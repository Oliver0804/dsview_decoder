import sigrokdecode as srd
from collections import namedtuple

Data = namedtuple('Data', ['ss', 'es', 'val'])

MAX30001_REGISTERS = {
    0x00: "NO_OP",
    0x01: "STATUS",
    0x02: "EN_INT",
    0x03: "EN_INT2",
    0x04: "MNGR_INT",
    0x05: "MNGR_DYN",
    0x08: "SW_RST",
    0x09: "SYNCH",
    0x0A: "FIFO_RST",
    0x0F: "INFO",
    0x10: "CNFG_GEN",
    0x12: "CNFG_CAL",
    0x14: "CNFG_EMUX",
    0x15: "CNFG_ECG",
    0x17: "CNFG_BMUX",
    0x18: "CNFG_BioZ",
    0x1A: "CNFG_PACE",
    0x1D: "CNFG_RTOR1",
    0x1E: "CNFG_RTOR2",
    0x20: "ECG_FIFO_BURST",
    0x21: "ECG_FIFO",
    0x22: "BIOZ_FIFO_BURST",
    0x23: "BIOZ_FIFO",
    0x25: "RTOR",
    0x30: "PACE0_BURST",
    0x31: "PACE0_A",
    0x32: "PACE0_B",
    0x33: "PACE0_C",
    0x34: "PACE1_BURST",
    0x35: "PACE1_A",
    0x36: "PACE1_B",
    0x37: "PACE1_C",
    0x38: "PACE2_BURST",
    0x39: "PACE2_A",
    0x3A: "PACE2_B",
    0x3B: "PACE2_C",
    0x3C: "PACE3_BURST",
    0x3D: "PACE3_A",
    0x3E: "PACE3_B",
    0x3F: "PACE3_C",
    0x40: "PACE4_BURST",
    0x41: "PACE4_A",
    0x42: "PACE4_B",
    0x43: "PACE4_C",
    0x44: "PACE5_BURST",
    0x45: "PACE5_A",
    0x46: "PACE5_B",
    0x47: "PACE5_C",
    0x7F: "NO_OP"
}

'''
OUTPUT_PYTHON format:

Packet:
[<ptype>, <data1>, <data2>]

<ptype>:
 - 'DATA': <data1> contains the MOSI data, <data2> contains the MISO data.
   The data is _usually_ 8 bits (but can also be fewer or more bits).
   Both data items are Python numbers (not strings), or None if the respective
   channel was not supplied.
 - 'BITS': <data1>/<data2> contain a list of bit values in this MOSI/MISO data
   item, and for each of those also their respective start-/endsample numbers.
 - 'CS-CHANGE': <data1> is the old CS# pin value, <data2> is the new value.
   Both data items are Python numbers (0/1), not strings. At the beginning of
   the decoding a packet is generated with <data1> = None and <data2> being the
   initial state of the CS# pin or None if the chip select pin is not supplied.
 - 'TRANSFER': <data1>/<data2> contain a list of Data() namedtuples for each
   byte transferred during this block of CS# asserted time. Each Data() has
   fields ss, es, and val.

Examples:
 ['CS-CHANGE', None, 1]
 ['CS-CHANGE', 1, 0]
 ['DATA', 0xff, 0x3a]
 ['BITS', [[1, 80, 82], [1, 83, 84], [1, 85, 86], [1, 87, 88],
           [1, 89, 90], [1, 91, 92], [1, 93, 94], [1, 95, 96]],
          [[0, 80, 82], [1, 83, 84], [0, 85, 86], [1, 87, 88],
           [1, 89, 90], [1, 91, 92], [0, 93, 94], [0, 95, 96]]]
 ['DATA', 0x65, 0x00]
 ['DATA', 0xa8, None]
 ['DATA', None, 0x55]
 ['CS-CHANGE', 0, 1]
 ['TRANSFER', [Data(ss=80, es=96, val=0xff), ...],
              [Data(ss=80, es=96, val=0x3a), ...]]
'''

# Key: (CPOL, CPHA). Value: SPI mode.
# Clock polarity (CPOL) = 0/1: Clock is low/high when inactive.
# Clock phase (CPHA) = 0/1: Data is valid on the leading/trailing clock edge.
spi_mode = {
    (0, 0): 0, # Mode 0
    (0, 1): 1, # Mode 1
    (1, 0): 2, # Mode 2
    (1, 1): 3, # Mode 3
}

class ChannelError(Exception):
    pass

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
        {'id': 'clk', 'type': 0, 'name': 'CLK', 'desc': 'Clock', 'idn':'dec_0spi_chan_clk'},
    )
    optional_channels = (
        {'id': 'miso', 'type': 107, 'name': 'MISO', 'desc': 'Master in, slave out', 'idn':'dec_0spi_opt_chan_miso'},
        {'id': 'mosi', 'type': 109, 'name': 'MOSI', 'desc': 'Master out, slave in', 'idn':'dec_0spi_opt_chan_mosi'},
        {'id': 'cs', 'type': -1, 'name': 'CS#', 'desc': 'Chip-select', 'idn':'dec_0spi_opt_chan_cs'},
    )
    options = (
        {'id': 'cs_polarity', 'desc': 'CS# polarity', 'default': 'active-low',
            'values': ('active-low', 'active-high'), 'idn':'dec_0spi_opt_cs_pol'},
        {'id': 'cpol', 'desc': 'Clock polarity (CPOL)', 'default': 0,
            'values': (0, 1), 'idn':'dec_0spi_opt_cpol'},
        {'id': 'cpha', 'desc': 'Clock phase (CPHA)', 'default': 0,
            'values': (0, 1), 'idn':'dec_0spi_opt_cpha'},
        {'id': 'bitorder', 'desc': 'Bit order',
            'default': 'msb-first', 'values': ('msb-first', 'lsb-first'), 'idn':'dec_0spi_opt_bitorder'},
        {'id': 'wordsize', 'desc': 'Word size', 'default': 8,
            'values': tuple(range(4,129,1)), 'idn':'dec_0spi_opt_wordsize'},
    )
    annotations = (
        ('106', 'miso-data', 'MISO data'),
        ('108', 'mosi-data', 'MOSI data'),
        ('reg', 'Register', 'Register Name'),  # Add this line
        ('write', 'MAX30001_Write', 'MAX30001 Write Data'),
        ('read', 'MAX30001_Read', 'MAX30001 Read Data'),


    )
    annotation_rows = (
        ('miso-data', 'MISO data', (0,)),
        ('mosi-data', 'MOSI data', (1,)),
        ('register-name', 'Register', (2,)), 
        ('max30001-write', 'MAX30001 Write', (3,)),
        ('max30001-read', 'MAX30001 Read', (4,)),


    )

    def __init__(self):
        self.reset()
        self.miso_buffer = []  # 重新命名為 miso_buffer
        self.mosi_buffer = []  # 新增 mosi_buffer

    def reset(self):
        self.samplerate = None
        self.bitcount = 0
        self.misodata = self.mosidata = 0
        self.misobits = []
        self.mosibits = []
        self.ss_block = -1
        self.samplenum = -1
        self.ss_transfer = -1
        self.cs_was_deasserted = False
        self.have_cs = self.have_miso = self.have_mosi = None
        self.miso_buffer = []  # 重新命名為 miso_buffer
        self.mosi_buffer = []  # 新增 mosi_buffer

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.bw = (self.options['wordsize'] + 7) // 8

    def metadata(self, key, value):
       if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def putw(self, data):
        self.put(self.ss_block, self.samplenum, self.out_ann, data)

    def putdata(self):
        so = self.misodata if self.have_miso else None
        si = self.mosidata if self.have_mosi else None

        # 原始 1-byte SPI 解碼
        if self.have_miso:
            ss, es = self.misobits[-1][1], self.misobits[0][2]
            self.put(ss, es, self.out_ann, [0, ['%02X' % self.misodata]])
            self.miso_buffer.append((self.misodata, ss, es))
            
        if self.have_mosi:
            ss, es = self.mosibits[-1][1], self.mosibits[0][2]
            self.put(ss, es, self.out_ann, [1, ['%02X' % self.mosidata]])
            self.mosi_buffer.append((self.mosidata, ss, es))

         # MAX30001 4-byte 解碼
        if len(self.mosi_buffer) == 4 and len(self.miso_buffer) == 4:
            start_ss = min(self.mosi_buffer[0][1], self.miso_buffer[0][1])
            end_es = max(self.mosi_buffer[3][2], self.miso_buffer[3][2])

            # 從 MOSI 第一個 byte 獲取讀寫位
            first_byte_mosi = self.mosi_buffer[0][0]
            address = (first_byte_mosi >> 1) & 0x7F  # 7-bit address
            rw_bit = first_byte_mosi & 0x01          # read/write bit

            # Get register name
            reg_name = MAX30001_REGISTERS.get(address, "UNKNOWN")
            
            # Add register name annotation
            suffix = '[R]' if rw_bit else '[W]'
            self.put(start_ss, end_es, self.out_ann, [2, [f'{reg_name}{suffix}']])
            
            # 根據讀寫位選擇數據來源
            if rw_bit:  # Read operation (r=1)，從 MISO 讀取數據
                data_value = 0
                for i in range(1, 4):
                    data_value |= (self.miso_buffer[i][0] << ((3-i) * 8))
                
                self.put(start_ss, end_es, self.out_ann,
                        [4, ['Read (0x%02X) Data:0x%06X' % (address, data_value)]])
            else:  # Write operation (r=0)，從 MOSI 讀取數據
                data_value = 0
                for i in range(1, 4):
                    data_value |= (self.mosi_buffer[i][0] << ((3-i) * 8))
                
                self.put(start_ss, end_es, self.out_ann,
                        [3, ['Write (0x%02X) Data:0x%06X' % (address, data_value)]])

            # 清空兩個 buffer
            self.mosi_buffer = []
            self.miso_buffer = []

    def reset_decoder_state(self):
        self.misodata = 0 if self.have_miso else None
        self.mosidata = 0 if self.have_mosi else None
        self.misobits = [] if self.have_miso else None
        self.mosibits = [] if self.have_mosi else None
        self.bitcount = 0

    def cs_asserted(self, cs):
        active_low = (self.options['cs_polarity'] == 'active-low')
        return (cs == 0) if active_low else (cs == 1)

    def handle_bit(self, miso, mosi, clk, cs):
        # If this is the first bit of a dataword, save its sample number.
        if self.bitcount == 0:
            self.ss_block = self.samplenum
            self.cs_was_deasserted = \
                not self.cs_asserted(cs) if self.have_cs else False

        ws = self.options['wordsize']
        bo = self.options['bitorder']

        # Receive MISO bit into our shift register.
        if self.have_miso:
            if bo == 'msb-first':
                self.misodata |= miso << (ws - 1 - self.bitcount)
            else:
                self.misodata |= miso << self.bitcount

        # Receive MOSI bit into our shift register.
        if self.have_mosi:
            if bo == 'msb-first':
                self.mosidata |= mosi << (ws - 1 - self.bitcount)
            else:
                self.mosidata |= mosi << self.bitcount

        # Guesstimate the endsample for this bit (can be overridden below).
        es = self.samplenum
        if self.bitcount > 0:
            if self.have_miso:
                es += self.samplenum - self.misobits[0][1]
            elif self.have_mosi:
                es += self.samplenum - self.mosibits[0][1]

        if self.have_miso:
            self.misobits.insert(0, [miso, self.samplenum, es])
        if self.have_mosi:
            self.mosibits.insert(0, [mosi, self.samplenum, es])

        if self.bitcount > 0 and self.have_miso:
            self.misobits[1][2] = self.samplenum
        if self.bitcount > 0 and self.have_mosi:
            self.mosibits[1][2] = self.samplenum

        self.bitcount += 1

        # Continue to receive if not enough bits were received, yet.
        if self.bitcount != ws:
            return

        self.putdata()

        self.reset_decoder_state()

    def find_clk_edge(self, miso, mosi, clk, cs, first):
        if self.have_cs and (first or (self.matched & (0b1 << self.have_cs))):
            # Send all CS# pin value changes.
            oldcs = None if first else 1 - cs

            # Reset decoder state when CS# changes (and the CS# pin is used).
            self.reset_decoder_state()

        # We only care about samples if CS# is asserted.
        if self.have_cs and not self.cs_asserted(cs):
            return

        # Ignore sample if the clock pin hasn't changed.
        if first or not (self.matched & (0b1 << 0)):
            return

        # Found the correct clock edge, now get the SPI bit(s).
        self.handle_bit(miso, mosi, clk, cs)

    def decode(self):
        # The CLK input is mandatory. Other signals are (individually)
        # optional. Yet either MISO or MOSI (or both) must be provided.
        # Tell stacked decoders when we don't have a CS# signal.
        if not self.has_channel(0):
            raise ChannelError('CLK pin required.')
        self.have_miso = self.has_channel(1)
        self.have_mosi = self.has_channel(2)
        if not self.have_miso and not self.have_mosi:
            raise ChannelError('Either MISO or MOSI (or both) pins required.')
        self.have_cs = self.has_channel(3)

        # We want all CLK changes. We want all CS changes if CS is used.
        # Map 'have_cs' from boolean to an integer index. This simplifies
        # evaluation in other locations.
        # Sample data on rising/falling clock edge (depends on mode).
        mode = spi_mode[self.options['cpol'], self.options['cpha']]
        if mode == 0 or mode == 3:   # Sample on rising clock edge
            wait_cond = [{0: 'r'}]
        else: # Sample on falling clock edge
            wait_cond = [{0: 'f'}]

        if self.have_cs:
            self.have_cs = len(wait_cond)
            wait_cond.append({3: 'e'})

        # "Pixel compatibility" with the v2 implementation. Grab and
        # process the very first sample before checking for edges. The
        # previous implementation did this by seeding old values with
        # None, which led to an immediate "change" in comparison.
        (clk, miso, mosi, cs) = self.wait({})
        self.find_clk_edge(miso, mosi, clk, cs, True)

        while True:
            (clk, miso, mosi, cs) = self.wait(wait_cond)
            self.find_clk_edge(miso, mosi, clk, cs, False)
