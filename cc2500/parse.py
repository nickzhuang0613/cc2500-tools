import operator
import binascii

def whitening_seq():
	v = 0x1ff
	while True:
		yield v & 0xff
		top = (v & 0x1e0)
		v = (top ^ (top >> 4) ^ (top >> 8) ^ (v << 1) ^ (v << 5)) & 0x1ff

def _crc(degree, poly, crcval, data, data_bits):
	crcval_msb = 1 << degree
	data_msb = 1 << data_bits
	for i in range(data_bits):
		data <<= 1
		crcval <<= 1
		if bool(crcval & crcval_msb) ^ bool(data & data_msb):
			crcval ^= poly
	return crcval

def crc16(data):
	return _crc(16, 0x8005, 0xffff, int(binascii.hexlify(data), 16), 8 * len(data)) & 0xffff

def get_sync_data(conf):
	preamble = b'\xAA'
	preamble *= [2, 3, 4, 6, 8, 12, 16, 24][conf.field.NUM_PREAMBLE]

	sync_word = bytes([conf.reg.SYNC1, conf.reg.SYNC0])
	sync_count = [0, 1, 1, 2][conf.field.SYNC_MODE % 4]

	sync_word *= sync_count
	if not sync_count:
		preamble *= 0

	return preamble, sync_word

def make_parser(conf):
	own_length = conf.field.PACKET_LENGTH
	addr_mode = conf.field.ADR_CHK
	white_data = conf.field.WHITE_DATA
	crc_en = conf.field.CRC_EN
	length_mode = conf.field.LENGTH_CONFIG
	own_addr = conf.field.DEVICE_ADDR

	assert not conf.field.CC2400_EN, 'CC2400 mode not supported (yet)'
	assert length_mode in {0, 1}, 'Infinite packet length not supported'
	assert not conf.field.MANCHESTER_EN, 'Manchester encoding not supported (yet)'
	assert not conf.field.FEC_EN, 'FEC not supported (yet)'

	preamble, sync_word = get_sync_data(conf)
	length_size = int(length_mode == 1)
	addr_size = int(addr_mode != 0)
	crc_size = 2 * crc_en

	valid_addrs = {own_addr}
	if addr_mode > 1:
		valid_addrs.add(0x00)
	if addr_mode > 2:
		valid_addrs.add(0xff)

	# The size that needs to be added to the length of the payload returned by parse() to get the full raw size
	base_size = len(preamble) + len(sync_word) + length_size + addr_size + crc_size

	def parse(data):
		assert data[:len(preamble)] == preamble
		data = data[len(preamble):]
		assert data[:len(sync_word)] == sync_word
		data = data[len(sync_word):]

		if white_data:
			data = bytes(map(operator.xor, data, whitening_seq()))

		length = own_length
		if length_size:
			length = data[0]
			assert length <= own_length

		addr = None
		if addr_size:
			addr = data[length_size]
			assert addr in valid_addrs

		if crc_en:
			data = data[:length_size+length+crc_size]
			assert crc16(data) == 0

		payload = data[length_size+addr_size:length_size+length]

		return (addr, payload)

	return base_size, parse

