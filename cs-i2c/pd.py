import sigrokdecode as srd

class Decoder(srd.Decoder):
    api_version = 3
    id = 'custom_i2c'
    name = 'Custom I2C Decoder'
    longname = 'Custom I2C Protocol Decoder'
    desc = 'A custom implementation of an I2C protocol decoder.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['i2c']
    tags = ['Embedded/industrial']
    channels = (
        {'id': 'scl', type: 0, 'name': 'SCL', 'desc': 'Clock Line'},
        {'id': 'sda', type: 1, 'name': 'SDA', 'desc': 'Data Line'},
    )
    optional_channels = ()
    options = (
        {'id': 'debug_bits', 'desc': 'Print each bit', 'default': 'no', 
            'values': ('yes', 'no')},
        {'id': 'wordsize', 'desc': 'Data word size (# bus cycles)', 'default': 8},
     )
    annotations = (
        ('bit', 'Data Bit', 'Single data bit captured'),
        ('byte_8', 'Data Byte (Write)', '8 bits combined into one byte'),
        ('byte_9', 'Data Byte (Read)', '9 bits combined into one byte, last bit discarded'),
    )
    annotation_rows = (
        ('data_bits', 'Data Bits', (0,)),
        ('data_bytes', 'Data Bytes', (1, 2)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.clk_count = 0
        self.current_byte = 0
        self.bit_count = 0
        self.start_sample = None
        self.last_rising_time = 0

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def put_annotation(self, start, end, annotation, data):
        self.put(start, end, self.out_ann, [annotation, data])

    def decode_i2c(self):
        while True:
            scl, sda = self.wait([{0: 'r'}, {1: 'e'}])

            if scl:  # On SCL rising edge, collect bits
                current_rising_time = self.samplenum
                if self.last_rising_time != 0 and (current_rising_time - self.last_rising_time) > 650:

                    if self.bit_count == 9:  
                        self.put_annotation(self.start_sample, self.samplenum+1, 1, [f'Byte (Read): 0x{self.current_byte>>1:02X}'])
                        self.current_byte = 0
                        self.bit_count = 0
                    elif self.bit_count == 8:  
                        self.put_annotation(self.start_sample, self.samplenum+1, 2, [f'Byte (Write): 0x{self.current_byte:02X}'])
                        self.current_byte = 0
                        self.bit_count = 0
                    self.current_byte = 0
                    self.bit_count = 0
                

                self.last_rising_time = current_rising_time

                if self.bit_count == 0:
                    self.start_sample = self.samplenum

                self.current_byte = (self.current_byte << 1) | sda
                self.bit_count += 1


    def decode(self):
        self.decode_i2c()
