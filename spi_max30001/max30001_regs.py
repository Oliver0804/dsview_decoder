# MAX30001 Register definitions
REGISTERS = {
    0x01: {'name': 'STATUS', 'desc': 'Status Register'},
    0x02: {'name': 'EN_INT', 'desc': 'Interrupt Enable Register'},
    0x03: {'name': 'EN_INT2', 'desc': 'Interrupt Enable Register 2'},
    0x04: {'name': 'MNGR_INT', 'desc': 'Interrupt Manager Register'},
    0x05: {'name': 'MNGR_DYN', 'desc': 'Dynamic Modes Register'},
    # 根據文件添加其他暫存器定義
}
