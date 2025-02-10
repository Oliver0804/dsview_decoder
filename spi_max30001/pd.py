import sigrokdecode as srd
from collections import namedtuple

# 新增數據結構定義
Data = namedtuple('Data', ['ss', 'es', 'val'])

class Decoder(srd.Decoder):
    api_version = 3
    id = 'max30001_spi'
    name = 'MAX30001 SPI'
    longname = 'MAX30001 ECG/AFE Decoder'
    desc = 'Decodes SPI transactions for MAX30001 ECG/AFE data.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['max30001']
    tags = ['Embedded/industrial']
    channels = (
        {'id': 'clk', 'type': 0, 'name': 'CLK', 'desc': 'Clock'},
        {'id': 'cs', 'type': -1, 'name': 'CS#', 'desc': 'Chip-select'},
    )
    optional_channels = (
        {'id': 'miso', 'type': 107, 'name': 'MISO', 'desc': 'Master in, slave out'},
        {'id': 'mosi', 'type': 109, 'name': 'MOSI', 'desc': 'Master out, slave in'},
    )
    options = (
        {'id': 'bitorder', 'desc': 'Bit order', 'default': 'msb-first', 'values': ('msb-first', 'lsb-first')},
    )
    annotations = (
        ('cmd', 'Command', 'SPI Command'),
        ('read', 'Read', 'SPI Read'),
        ('write', 'Write', 'SPI Write'),
        ('data_r', 'Data Read', 'SPI Data Read'),
        ('data_w', 'Data Write', 'SPI Data Write'),
        ('miso', 'MISO', 'MISO Data'),  # 新增 MISO 數據顯示
        ('mosi', 'MOSI', 'MOSI Data'),  # 新增 MOSI 數據顯示
    )
    annotation_rows = (
        ('commands', 'Commands', (0,)),
        ('read', 'Read', (1,)),
        ('write', 'Write', (2,)),
        ('data_r', 'Data Read', (3,)),
        ('data_w', 'Data Write', (4,)),
        ('raw_data', 'Raw Data', (5, 6)),  # 新增原始數據行
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.bitcount = 0
        self.word = 0
        self.bytecount = 0
        self.transaction = []
        self.cs_active = False
        self.start_sample = None
        self.rw_flag = None
        self.word_miso = 0
        self.word_mosi = 0
        self.transaction_miso = []
        self.transaction_mosi = []

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_python = self.register(srd.OUTPUT_PYTHON)  # 註冊 Python 輸出
        # 確認必要的通道存在
        if not self.has_channel(0):
            raise ChannelError('需要 CLK 通道')
        self.have_miso = self.has_channel(1)
        self.have_mosi = self.has_channel(2)
        if not self.have_miso and not self.have_mosi:
            raise ChannelError('需要 MISO 或 MOSI 通道')

    def put_annot(self, ss, es, ann_type, text):
        self.put(ss, es, self.out_ann, [ann_type, [text]])

    def put_python_data(self, ss, es, data_type, data1, data2=None):
        """輸出 Python 格式數據"""
        self.put(ss, es, self.out_python, [data_type, data1, data2])

    def decode(self):
        while True:
            # 等待時鐘上升沿和 CS 變化
            wait_cond = [{0: 'r'}]  # CLK 上升沿
            if self.has_channel(3):  # 如果有 CS 通道
                wait_cond.append({3: 'e'})  # CS 邊緣變化

            (clk, miso, mosi, cs) = self.wait(wait_cond)
            
            if cs == 0 and not self.cs_active:
                # CS 變化時輸出狀態
                self.put_python_data(self.samplenum, self.samplenum,
                                   'CS-CHANGE', None if self.start_sample is None else 1, 0)
                self.cs_active = True
                self.bitcount = 0
                self.word_miso = 0
                self.word_mosi = 0
                self.bytecount = 0
                self.transaction_miso = []
                self.transaction_mosi = []
                self.start_sample = self.samplenum
                self.rw_flag = None
            
            # 只在 CS 有效且時鐘為上升沿時採樣
            if self.cs_active and clk == 1:
                # 確保有效的信號讀取
                bit_miso = miso if self.have_miso else 0
                bit_mosi = mosi if self.have_mosi else 0

                # 記錄採樣點
                sample_point = self.samplenum

                # 同時處理 MISO 和 MOSI，確保兩路數據都被正確採樣
                if self.options['bitorder'] == 'msb-first':
                    if self.have_miso:
                        self.word_miso = (self.word_miso << 1) | (bit_miso & 0x1)
                    if self.have_mosi:
                        self.word_mosi = (self.word_mosi << 1) | (bit_mosi & 0x1)
                else:
                    if self.have_miso:
                        self.word_miso |= (bit_miso & 0x1) << self.bitcount
                    if self.have_mosi:
                        self.word_mosi |= (bit_mosi & 0x1) << self.bitcount

                self.bitcount += 1
                
                if self.bitcount == 8:
                    # 輸出每個字節的數據
                    if self.bytecount > 0:
                        self.put_python_data(self.start_sample, self.samplenum,
                                           'DATA', self.word_mosi, self.word_miso)

                    # 首字節特殊處理
                    if self.bytecount == 0:
                        # 確保從 MOSI 讀取讀寫標誌
                        self.rw_flag = self.word_mosi & 0x01
                        addr = self.word_mosi >> 1
                        self.put_annot(self.start_sample, self.samplenum, 0,
                                     f'Addr: 0x{addr:02X}, {"Read" if self.rw_flag else "Write"}')

                    # 保存兩路數據
                    self.transaction_miso.append(self.word_miso)
                    self.transaction_mosi.append(self.word_mosi)
                    
                    self.word_miso = 0
                    self.word_mosi = 0
                    self.bitcount = 0
                    self.bytecount += 1
                    
                    if self.bytecount == 4:
                        # 輸出完整傳輸數據
                        mosi_data = []
                        miso_data = []
                        for i in range(4):
                            byte_ss = self.start_sample + (i * 8)
                            byte_es = byte_ss + 8
                            mosi_data.append(Data(byte_ss, byte_es, self.transaction_mosi[i]))
                            miso_data.append(Data(byte_ss, byte_es, self.transaction_miso[i]))
                        
                        self.put_python_data(self.start_sample, self.samplenum,
                                           'TRANSFER', mosi_data, miso_data)

                        # 根據讀寫標誌決定要顯示的數據
                        if self.rw_flag:
                            # 讀取操作：只顯示 MISO 數據
                            data_miso = (self.transaction_miso[1] << 16) | \
                                      (self.transaction_miso[2] << 8) | \
                                      self.transaction_miso[3]
                            self.put_annot(self.start_sample, self.samplenum, 3,
                                         f'Data Read: 0x{data_miso:06X}')
                        else:
                            # 寫入操作：只顯示 MOSI 數據
                            data_mosi = (self.transaction_mosi[1] << 16) | \
                                      (self.transaction_mosi[2] << 8) | \
                                      self.transaction_mosi[3]
                            self.put_annot(self.start_sample, self.samplenum, 4,
                                         f'Data Write: 0x{data_mosi:06X}')
                        
                        # CS 釋放時輸出狀態
                        self.put_python_data(self.samplenum, self.samplenum,
                                           'CS-CHANGE', 0, 1)
                        self.cs_active = False
