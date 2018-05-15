import os
import numpy as np
import pandas as pd
import datetime as dt
import torch
from geopy.distance import geodesic
import logging
import pickle
import sklearn
from sklearn import preprocessing
from collections import OrderedDict

DBG = 1

DECODE_STEPS = 48
USE_CUDA = True
device = torch.device("cuda" if USE_CUDA else "cpu")

whether_list = ['EMPTY', 'CLEAR_NIGHT', 'SNOW', 'RAIN', 'PARTLY_CLOUDY_DAY', 'HAZE',
                'CLEAR_DAY', 'PARTLY_CLOUDY_NIGHT', 'WIND', 'CLOUDY']
whether_le = preprocessing.LabelEncoder()
whether_le.fit(whether_list)

bj_stations = [
    'aotizhongxin_aq', 'badaling_aq', 'beibuxinqu_aq', 'daxing_aq',
    'dingling_aq', 'donggaocun_aq', 'dongsi_aq', 'dongsihuan_aq',
    'fangshan_aq', 'fengtaihuayuan_aq', 'guanyuan_aq', 'gucheng_aq',
    'huairou_aq', 'liulihe_aq', 'mentougou_aq', 'miyun_aq',
    'miyunshuiku_aq', 'nansanhuan_aq', 'nongzhanguan_aq',
    'pingchang_aq', 'pinggu_aq', 'qianmen_aq', 'shunyi_aq',
    'tiantan_aq', 'tongzhou_aq', 'wanliu_aq', 'wanshouxigong_aq',
    'xizhimenbei_aq', 'yanqin_aq', 'yizhuang_aq', 'yongdingmennei_aq',
    'yongledian_aq', 'yufa_aq', 'yungang_aq', 'zhiwuyuan_aq']

ld_stations = ['BL0', 'CD9', 'CD1', 'GN0', 'GR4', 'GN3', 'GR9', 'HV1', 'KF1', 'LW2', 'ST5', 'TH4',
               'MY7', 'BX9', 'BX1', 'CT2', 'CT3', 'CR8', 'GB0', 'HR1', 'LH0', 'KC1', 'RB7', 'TD5']
# ld_stations = ['BL0', 'CD9', 'CD1', 'GN0', 'GR4', 'GN3', 'GR9', 'HV1', 'KF1', 'LW2', 'ST5', 'TH4',
#               'MY7', 'BX9', 'BX1', 'CT2', 'CT3']
aq_stations = bj_stations + ld_stations
aq_le = preprocessing.LabelEncoder()
aq_le.fit(aq_stations)

bj_latitude0 = 39.0
bj_longitude0 = 115.0
bj_origin = (bj_latitude0, bj_longitude0)
ld_latitude0 = 50.5
ld_longitude0 = -2.0
ld_origin = (ld_latitude0, ld_longitude0)
origin_list = [bj_origin, ld_origin]


def cal_pos(point, origin):
    x = geodesic(origin, (origin[0], point[1])).kilometers
    y = geodesic((point[0], origin[1]), origin).kilometers
    return x, y


# print(cal_pos((39.1, 115.1), bj_origin))
# print(cal_pos((50.6, -1.9), ld_origin))

'''
def cal_grid_pos():
    grid_pos = OrderedDict()
    grid_ll = []
    grid_ll.append(pd.read_csv('../input/Beijing_grid_weather_station.csv'))
    grid_ll.append(pd.read_csv('../input/London_grid_weather_station.csv'))

    for city in (0, 1):
        for k in range(len(grid_ll[city])):
            station_id = grid_ll[city].StationId[k]
            latitude = grid_ll[city].Latitude[k]
            longitude = grid_ll[city].Longitude[k]
            pos = cal_pos((latitude, longitude), origin_list[city])
            grid_pos[station_id] = pos
    return grid_pos
'''


def cal_st_pos():
    st_pos = OrderedDict()
    st_files = [
        ['../input/Beijing_AirQuality_Stations_cn.csv', 0],
        ['../input/London_AirQuality_Stations.csv', 1],
        ['../input/Beijing_grid_weather_station.csv', 0],
        ['../input/London_grid_weather_station.csv', 1],
    ]
    for file, city in st_files:
        # print(file)
        st_info = pd.read_csv(file)
        for k in range(len(st_info)):
            station_id = st_info.StationId[k]
            latitude = st_info.Latitude[k]
            longitude = st_info.Longitude[k]
            pos = cal_pos((latitude, longitude), origin_list[city])
            st_pos[station_id] = pos
            # print(station_id, pos)
    return st_pos


st_pos_dict = cal_st_pos()


def get_st_x(station_id):
    return st_pos_dict[station_id][0]


def get_st_y(station_id):
    return st_pos_dict[station_id][1]


def now2str(format="%Y-%m-%d_%H-%M-%S-%f"):
    return dt.datetime.now().strftime(format)


def save_dump(dump_data, out_file):
    with open(out_file, 'wb') as fp:
        print('Writing to %s.' % out_file)
        # pickle.dump(dump_data, fp, pickle.HIGHEST_PROTOCOL)
        pickle.dump(dump_data, fp)


def load_dump(dump_file):
    fp = open(dump_file, 'rb')
    if not fp:
        print('Fail to open the dump file: %s' % dump_file)
        return None
    dump = pickle.load(fp)
    fp.close()
    return dump


def init_logger(name='td', to_console=True, log_file=None, level=logging.DEBUG,
                msg_fmt='[%(asctime)s]  %(message)s', time_fmt="%Y-%m-%d %H:%M:%S"):
    # create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # create formatter
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', "%Y-%m-%d %H:%M:%S")
    formatter = logging.Formatter(msg_fmt, time_fmt)

    if logger.handlers != [] and isinstance(logger.handlers[0], logging.StreamHandler):
        logger.handlers.pop(0)
    # create console handler and set level to debug
    f = open("/tmp/debug", "w")  # example handler
    if to_console:
        f = None

    ch = logging.StreamHandler(f)
    ch.setLevel(level)
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)

    if log_file:
        fh = logging.FileHandler(log_file, mode='a', encoding=None, delay=False)
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger

#get directory size recursively
def get_dir_size(path='.'):
    total = 0
    for entry in os.scandir(path):
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            total += get_dir_size(entry.path)
    return total


bj_grids = [
    'beijing_grid_000', 'beijing_grid_001', 'beijing_grid_002',
    'beijing_grid_003', 'beijing_grid_004', 'beijing_grid_005',
    'beijing_grid_006', 'beijing_grid_007', 'beijing_grid_008',
    'beijing_grid_009', 'beijing_grid_010', 'beijing_grid_011',
    'beijing_grid_012', 'beijing_grid_013', 'beijing_grid_014',
    'beijing_grid_015', 'beijing_grid_016', 'beijing_grid_017',
    'beijing_grid_018', 'beijing_grid_019', 'beijing_grid_020',
    'beijing_grid_021', 'beijing_grid_022', 'beijing_grid_023',
    'beijing_grid_024', 'beijing_grid_025', 'beijing_grid_026',
    'beijing_grid_027', 'beijing_grid_028', 'beijing_grid_029',
    'beijing_grid_030', 'beijing_grid_031', 'beijing_grid_032',
    'beijing_grid_033', 'beijing_grid_034', 'beijing_grid_035',
    'beijing_grid_036', 'beijing_grid_037', 'beijing_grid_038',
    'beijing_grid_039', 'beijing_grid_040', 'beijing_grid_041',
    'beijing_grid_042', 'beijing_grid_043', 'beijing_grid_044',
    'beijing_grid_045', 'beijing_grid_046', 'beijing_grid_047',
    'beijing_grid_048', 'beijing_grid_049', 'beijing_grid_050',
    'beijing_grid_051', 'beijing_grid_052', 'beijing_grid_053',
    'beijing_grid_054', 'beijing_grid_055', 'beijing_grid_056',
    'beijing_grid_057', 'beijing_grid_058', 'beijing_grid_059',
    'beijing_grid_060', 'beijing_grid_061', 'beijing_grid_062',
    'beijing_grid_063', 'beijing_grid_064', 'beijing_grid_065',
    'beijing_grid_066', 'beijing_grid_067', 'beijing_grid_068',
    'beijing_grid_069', 'beijing_grid_070', 'beijing_grid_071',
    'beijing_grid_072', 'beijing_grid_073', 'beijing_grid_074',
    'beijing_grid_075', 'beijing_grid_076', 'beijing_grid_077',
    'beijing_grid_078', 'beijing_grid_079', 'beijing_grid_080',
    'beijing_grid_081', 'beijing_grid_082', 'beijing_grid_083',
    'beijing_grid_084', 'beijing_grid_085', 'beijing_grid_086',
    'beijing_grid_087', 'beijing_grid_088', 'beijing_grid_089',
    'beijing_grid_090', 'beijing_grid_091', 'beijing_grid_092',
    'beijing_grid_093', 'beijing_grid_094', 'beijing_grid_095',
    'beijing_grid_096', 'beijing_grid_097', 'beijing_grid_098',
    'beijing_grid_099', 'beijing_grid_100', 'beijing_grid_101',
    'beijing_grid_102', 'beijing_grid_103', 'beijing_grid_104',
    'beijing_grid_105', 'beijing_grid_106', 'beijing_grid_107',
    'beijing_grid_108', 'beijing_grid_109', 'beijing_grid_110',
    'beijing_grid_111', 'beijing_grid_112', 'beijing_grid_113',
    'beijing_grid_114', 'beijing_grid_115', 'beijing_grid_116',
    'beijing_grid_117', 'beijing_grid_118', 'beijing_grid_119',
    'beijing_grid_120', 'beijing_grid_121', 'beijing_grid_122',
    'beijing_grid_123', 'beijing_grid_124', 'beijing_grid_125',
    'beijing_grid_126', 'beijing_grid_127', 'beijing_grid_128',
    'beijing_grid_129', 'beijing_grid_130', 'beijing_grid_131',
    'beijing_grid_132', 'beijing_grid_133', 'beijing_grid_134',
    'beijing_grid_135', 'beijing_grid_136', 'beijing_grid_137',
    'beijing_grid_138', 'beijing_grid_139', 'beijing_grid_140',
    'beijing_grid_141', 'beijing_grid_142', 'beijing_grid_143',
    'beijing_grid_144', 'beijing_grid_145', 'beijing_grid_146',
    'beijing_grid_147', 'beijing_grid_148', 'beijing_grid_149',
    'beijing_grid_150', 'beijing_grid_151', 'beijing_grid_152',
    'beijing_grid_153', 'beijing_grid_154', 'beijing_grid_155',
    'beijing_grid_156', 'beijing_grid_157', 'beijing_grid_158',
    'beijing_grid_159', 'beijing_grid_160', 'beijing_grid_161',
    'beijing_grid_162', 'beijing_grid_163', 'beijing_grid_164',
    'beijing_grid_165', 'beijing_grid_166', 'beijing_grid_167',
    'beijing_grid_168', 'beijing_grid_169', 'beijing_grid_170',
    'beijing_grid_171', 'beijing_grid_172', 'beijing_grid_173',
    'beijing_grid_174', 'beijing_grid_175', 'beijing_grid_176',
    'beijing_grid_177', 'beijing_grid_178', 'beijing_grid_179',
    'beijing_grid_180', 'beijing_grid_181', 'beijing_grid_182',
    'beijing_grid_183', 'beijing_grid_184', 'beijing_grid_185',
    'beijing_grid_186', 'beijing_grid_187', 'beijing_grid_188',
    'beijing_grid_189', 'beijing_grid_190', 'beijing_grid_191',
    'beijing_grid_192', 'beijing_grid_193', 'beijing_grid_194',
    'beijing_grid_195', 'beijing_grid_196', 'beijing_grid_197',
    'beijing_grid_198', 'beijing_grid_199', 'beijing_grid_200',
    'beijing_grid_201', 'beijing_grid_202', 'beijing_grid_203',
    'beijing_grid_204', 'beijing_grid_205', 'beijing_grid_206',
    'beijing_grid_207', 'beijing_grid_208', 'beijing_grid_209',
    'beijing_grid_210', 'beijing_grid_211', 'beijing_grid_212',
    'beijing_grid_213', 'beijing_grid_214', 'beijing_grid_215',
    'beijing_grid_216', 'beijing_grid_217', 'beijing_grid_218',
    'beijing_grid_219', 'beijing_grid_220', 'beijing_grid_221',
    'beijing_grid_222', 'beijing_grid_223', 'beijing_grid_224',
    'beijing_grid_225', 'beijing_grid_226', 'beijing_grid_227',
    'beijing_grid_228', 'beijing_grid_229', 'beijing_grid_230',
    'beijing_grid_231', 'beijing_grid_232', 'beijing_grid_233',
    'beijing_grid_234', 'beijing_grid_235', 'beijing_grid_236',
    'beijing_grid_237', 'beijing_grid_238', 'beijing_grid_239',
    'beijing_grid_240', 'beijing_grid_241', 'beijing_grid_242',
    'beijing_grid_243', 'beijing_grid_244', 'beijing_grid_245',
    'beijing_grid_246', 'beijing_grid_247', 'beijing_grid_248',
    'beijing_grid_249', 'beijing_grid_250', 'beijing_grid_251',
    'beijing_grid_252', 'beijing_grid_253', 'beijing_grid_254',
    'beijing_grid_255', 'beijing_grid_256', 'beijing_grid_257',
    'beijing_grid_258', 'beijing_grid_259', 'beijing_grid_260',
    'beijing_grid_261', 'beijing_grid_262', 'beijing_grid_263',
    'beijing_grid_264', 'beijing_grid_265', 'beijing_grid_266',
    'beijing_grid_267', 'beijing_grid_268', 'beijing_grid_269',
    'beijing_grid_270', 'beijing_grid_271', 'beijing_grid_272',
    'beijing_grid_273', 'beijing_grid_274', 'beijing_grid_275',
    'beijing_grid_276', 'beijing_grid_277', 'beijing_grid_278',
    'beijing_grid_279', 'beijing_grid_280', 'beijing_grid_281',
    'beijing_grid_282', 'beijing_grid_283', 'beijing_grid_284',
    'beijing_grid_285', 'beijing_grid_286', 'beijing_grid_287',
    'beijing_grid_288', 'beijing_grid_289', 'beijing_grid_290',
    'beijing_grid_291', 'beijing_grid_292', 'beijing_grid_293',
    'beijing_grid_294', 'beijing_grid_295', 'beijing_grid_296',
    'beijing_grid_297', 'beijing_grid_298', 'beijing_grid_299',
    'beijing_grid_300', 'beijing_grid_301', 'beijing_grid_302',
    'beijing_grid_303', 'beijing_grid_304', 'beijing_grid_305',
    'beijing_grid_306', 'beijing_grid_307', 'beijing_grid_308',
    'beijing_grid_309', 'beijing_grid_310', 'beijing_grid_311',
    'beijing_grid_312', 'beijing_grid_313', 'beijing_grid_314',
    'beijing_grid_315', 'beijing_grid_316', 'beijing_grid_317',
    'beijing_grid_318', 'beijing_grid_319', 'beijing_grid_320',
    'beijing_grid_321', 'beijing_grid_322', 'beijing_grid_323',
    'beijing_grid_324', 'beijing_grid_325', 'beijing_grid_326',
    'beijing_grid_327', 'beijing_grid_328', 'beijing_grid_329',
    'beijing_grid_330', 'beijing_grid_331', 'beijing_grid_332',
    'beijing_grid_333', 'beijing_grid_334', 'beijing_grid_335',
    'beijing_grid_336', 'beijing_grid_337', 'beijing_grid_338',
    'beijing_grid_339', 'beijing_grid_340', 'beijing_grid_341',
    'beijing_grid_342', 'beijing_grid_343', 'beijing_grid_344',
    'beijing_grid_345', 'beijing_grid_346', 'beijing_grid_347',
    'beijing_grid_348', 'beijing_grid_349', 'beijing_grid_350',
    'beijing_grid_351', 'beijing_grid_352', 'beijing_grid_353',
    'beijing_grid_354', 'beijing_grid_355', 'beijing_grid_356',
    'beijing_grid_357', 'beijing_grid_358', 'beijing_grid_359',
    'beijing_grid_360', 'beijing_grid_361', 'beijing_grid_362',
    'beijing_grid_363', 'beijing_grid_364', 'beijing_grid_365',
    'beijing_grid_366', 'beijing_grid_367', 'beijing_grid_368',
    'beijing_grid_369', 'beijing_grid_370', 'beijing_grid_371',
    'beijing_grid_372', 'beijing_grid_373', 'beijing_grid_374',
    'beijing_grid_375', 'beijing_grid_376', 'beijing_grid_377',
    'beijing_grid_378', 'beijing_grid_379', 'beijing_grid_380',
    'beijing_grid_381', 'beijing_grid_382', 'beijing_grid_383',
    'beijing_grid_384', 'beijing_grid_385', 'beijing_grid_386',
    'beijing_grid_387', 'beijing_grid_388', 'beijing_grid_389',
    'beijing_grid_390', 'beijing_grid_391', 'beijing_grid_392',
    'beijing_grid_393', 'beijing_grid_394', 'beijing_grid_395',
    'beijing_grid_396', 'beijing_grid_397', 'beijing_grid_398',
    'beijing_grid_399', 'beijing_grid_400', 'beijing_grid_401',
    'beijing_grid_402', 'beijing_grid_403', 'beijing_grid_404',
    'beijing_grid_405', 'beijing_grid_406', 'beijing_grid_407',
    'beijing_grid_408', 'beijing_grid_409', 'beijing_grid_410',
    'beijing_grid_411', 'beijing_grid_412', 'beijing_grid_413',
    'beijing_grid_414', 'beijing_grid_415', 'beijing_grid_416',
    'beijing_grid_417', 'beijing_grid_418', 'beijing_grid_419',
    'beijing_grid_420', 'beijing_grid_421', 'beijing_grid_422',
    'beijing_grid_423', 'beijing_grid_424', 'beijing_grid_425',
    'beijing_grid_426', 'beijing_grid_427', 'beijing_grid_428',
    'beijing_grid_429', 'beijing_grid_430', 'beijing_grid_431',
    'beijing_grid_432', 'beijing_grid_433', 'beijing_grid_434',
    'beijing_grid_435', 'beijing_grid_436', 'beijing_grid_437',
    'beijing_grid_438', 'beijing_grid_439', 'beijing_grid_440',
    'beijing_grid_441', 'beijing_grid_442', 'beijing_grid_443',
    'beijing_grid_444', 'beijing_grid_445', 'beijing_grid_446',
    'beijing_grid_447', 'beijing_grid_448', 'beijing_grid_449',
    'beijing_grid_450', 'beijing_grid_451', 'beijing_grid_452',
    'beijing_grid_453', 'beijing_grid_454', 'beijing_grid_455',
    'beijing_grid_456', 'beijing_grid_457', 'beijing_grid_458',
    'beijing_grid_459', 'beijing_grid_460', 'beijing_grid_461',
    'beijing_grid_462', 'beijing_grid_463', 'beijing_grid_464',
    'beijing_grid_465', 'beijing_grid_466', 'beijing_grid_467',
    'beijing_grid_468', 'beijing_grid_469', 'beijing_grid_470',
    'beijing_grid_471', 'beijing_grid_472', 'beijing_grid_473',
    'beijing_grid_474', 'beijing_grid_475', 'beijing_grid_476',
    'beijing_grid_477', 'beijing_grid_478', 'beijing_grid_479',
    'beijing_grid_480', 'beijing_grid_481', 'beijing_grid_482',
    'beijing_grid_483', 'beijing_grid_484', 'beijing_grid_485',
    'beijing_grid_486', 'beijing_grid_487', 'beijing_grid_488',
    'beijing_grid_489', 'beijing_grid_490', 'beijing_grid_491',
    'beijing_grid_492', 'beijing_grid_493', 'beijing_grid_494',
    'beijing_grid_495', 'beijing_grid_496', 'beijing_grid_497',
    'beijing_grid_498', 'beijing_grid_499', 'beijing_grid_500',
    'beijing_grid_501', 'beijing_grid_502', 'beijing_grid_503',
    'beijing_grid_504', 'beijing_grid_505', 'beijing_grid_506',
    'beijing_grid_507', 'beijing_grid_508', 'beijing_grid_509',
    'beijing_grid_510', 'beijing_grid_511', 'beijing_grid_512',
    'beijing_grid_513', 'beijing_grid_514', 'beijing_grid_515',
    'beijing_grid_516', 'beijing_grid_517', 'beijing_grid_518',
    'beijing_grid_519', 'beijing_grid_520', 'beijing_grid_521',
    'beijing_grid_522', 'beijing_grid_523', 'beijing_grid_524',
    'beijing_grid_525', 'beijing_grid_526', 'beijing_grid_527',
    'beijing_grid_528', 'beijing_grid_529', 'beijing_grid_530',
    'beijing_grid_531', 'beijing_grid_532', 'beijing_grid_533',
    'beijing_grid_534', 'beijing_grid_535', 'beijing_grid_536',
    'beijing_grid_537', 'beijing_grid_538', 'beijing_grid_539',
    'beijing_grid_540', 'beijing_grid_541', 'beijing_grid_542',
    'beijing_grid_543', 'beijing_grid_544', 'beijing_grid_545',
    'beijing_grid_546', 'beijing_grid_547', 'beijing_grid_548',
    'beijing_grid_549', 'beijing_grid_550', 'beijing_grid_551',
    'beijing_grid_552', 'beijing_grid_553', 'beijing_grid_554',
    'beijing_grid_555', 'beijing_grid_556', 'beijing_grid_557',
    'beijing_grid_558', 'beijing_grid_559', 'beijing_grid_560',
    'beijing_grid_561', 'beijing_grid_562', 'beijing_grid_563',
    'beijing_grid_564', 'beijing_grid_565', 'beijing_grid_566',
    'beijing_grid_567', 'beijing_grid_568', 'beijing_grid_569',
    'beijing_grid_570', 'beijing_grid_571', 'beijing_grid_572',
    'beijing_grid_573', 'beijing_grid_574', 'beijing_grid_575',
    'beijing_grid_576', 'beijing_grid_577', 'beijing_grid_578',
    'beijing_grid_579', 'beijing_grid_580', 'beijing_grid_581',
    'beijing_grid_582', 'beijing_grid_583', 'beijing_grid_584',
    'beijing_grid_585', 'beijing_grid_586', 'beijing_grid_587',
    'beijing_grid_588', 'beijing_grid_589', 'beijing_grid_590',
    'beijing_grid_591', 'beijing_grid_592', 'beijing_grid_593',
    'beijing_grid_594', 'beijing_grid_595', 'beijing_grid_596',
    'beijing_grid_597', 'beijing_grid_598', 'beijing_grid_599',
    'beijing_grid_600', 'beijing_grid_601', 'beijing_grid_602',
    'beijing_grid_603', 'beijing_grid_604', 'beijing_grid_605',
    'beijing_grid_606', 'beijing_grid_607', 'beijing_grid_608',
    'beijing_grid_609', 'beijing_grid_610', 'beijing_grid_611',
    'beijing_grid_612', 'beijing_grid_613', 'beijing_grid_614',
    'beijing_grid_615', 'beijing_grid_616', 'beijing_grid_617',
    'beijing_grid_618', 'beijing_grid_619', 'beijing_grid_620',
    'beijing_grid_621', 'beijing_grid_622', 'beijing_grid_623',
    'beijing_grid_624', 'beijing_grid_625', 'beijing_grid_626',
    'beijing_grid_627', 'beijing_grid_628', 'beijing_grid_629',
    'beijing_grid_630', 'beijing_grid_631', 'beijing_grid_632',
    'beijing_grid_633', 'beijing_grid_634', 'beijing_grid_635',
    'beijing_grid_636', 'beijing_grid_637', 'beijing_grid_638',
    'beijing_grid_639', 'beijing_grid_640', 'beijing_grid_641',
    'beijing_grid_642', 'beijing_grid_643', 'beijing_grid_644',
    'beijing_grid_645', 'beijing_grid_646', 'beijing_grid_647',
    'beijing_grid_648', 'beijing_grid_649', 'beijing_grid_650']

ld_grids = [
    'london_grid_000', 'london_grid_001', 'london_grid_002',
    'london_grid_003', 'london_grid_004', 'london_grid_005',
    'london_grid_006', 'london_grid_007', 'london_grid_008',
    'london_grid_009', 'london_grid_010', 'london_grid_011',
    'london_grid_012', 'london_grid_013', 'london_grid_014',
    'london_grid_015', 'london_grid_016', 'london_grid_017',
    'london_grid_018', 'london_grid_019', 'london_grid_020',
    'london_grid_021', 'london_grid_022', 'london_grid_023',
    'london_grid_024', 'london_grid_025', 'london_grid_026',
    'london_grid_027', 'london_grid_028', 'london_grid_029',
    'london_grid_030', 'london_grid_031', 'london_grid_032',
    'london_grid_033', 'london_grid_034', 'london_grid_035',
    'london_grid_036', 'london_grid_037', 'london_grid_038',
    'london_grid_039', 'london_grid_040', 'london_grid_041',
    'london_grid_042', 'london_grid_043', 'london_grid_044',
    'london_grid_045', 'london_grid_046', 'london_grid_047',
    'london_grid_048', 'london_grid_049', 'london_grid_050',
    'london_grid_051', 'london_grid_052', 'london_grid_053',
    'london_grid_054', 'london_grid_055', 'london_grid_056',
    'london_grid_057', 'london_grid_058', 'london_grid_059',
    'london_grid_060', 'london_grid_061', 'london_grid_062',
    'london_grid_063', 'london_grid_064', 'london_grid_065',
    'london_grid_066', 'london_grid_067', 'london_grid_068',
    'london_grid_069', 'london_grid_070', 'london_grid_071',
    'london_grid_072', 'london_grid_073', 'london_grid_074',
    'london_grid_075', 'london_grid_076', 'london_grid_077',
    'london_grid_078', 'london_grid_079', 'london_grid_080',
    'london_grid_081', 'london_grid_082', 'london_grid_083',
    'london_grid_084', 'london_grid_085', 'london_grid_086',
    'london_grid_087', 'london_grid_088', 'london_grid_089',
    'london_grid_090', 'london_grid_091', 'london_grid_092',
    'london_grid_093', 'london_grid_094', 'london_grid_095',
    'london_grid_096', 'london_grid_097', 'london_grid_098',
    'london_grid_099', 'london_grid_100', 'london_grid_101',
    'london_grid_102', 'london_grid_103', 'london_grid_104',
    'london_grid_105', 'london_grid_106', 'london_grid_107',
    'london_grid_108', 'london_grid_109', 'london_grid_110',
    'london_grid_111', 'london_grid_112', 'london_grid_113',
    'london_grid_114', 'london_grid_115', 'london_grid_116',
    'london_grid_117', 'london_grid_118', 'london_grid_119',
    'london_grid_120', 'london_grid_121', 'london_grid_122',
    'london_grid_123', 'london_grid_124', 'london_grid_125',
    'london_grid_126', 'london_grid_127', 'london_grid_128',
    'london_grid_129', 'london_grid_130', 'london_grid_131',
    'london_grid_132', 'london_grid_133', 'london_grid_134',
    'london_grid_135', 'london_grid_136', 'london_grid_137',
    'london_grid_138', 'london_grid_139', 'london_grid_140',
    'london_grid_141', 'london_grid_142', 'london_grid_143',
    'london_grid_144', 'london_grid_145', 'london_grid_146',
    'london_grid_147', 'london_grid_148', 'london_grid_149',
    'london_grid_150', 'london_grid_151', 'london_grid_152',
    'london_grid_153', 'london_grid_154', 'london_grid_155',
    'london_grid_156', 'london_grid_157', 'london_grid_158',
    'london_grid_159', 'london_grid_160', 'london_grid_161',
    'london_grid_162', 'london_grid_163', 'london_grid_164',
    'london_grid_165', 'london_grid_166', 'london_grid_167',
    'london_grid_168', 'london_grid_169', 'london_grid_170',
    'london_grid_171', 'london_grid_172', 'london_grid_173',
    'london_grid_174', 'london_grid_175', 'london_grid_176',
    'london_grid_177', 'london_grid_178', 'london_grid_179',
    'london_grid_180', 'london_grid_181', 'london_grid_182',
    'london_grid_183', 'london_grid_184', 'london_grid_185',
    'london_grid_186', 'london_grid_187', 'london_grid_188',
    'london_grid_189', 'london_grid_190', 'london_grid_191',
    'london_grid_192', 'london_grid_193', 'london_grid_194',
    'london_grid_195', 'london_grid_196', 'london_grid_197',
    'london_grid_198', 'london_grid_199', 'london_grid_200',
    'london_grid_201', 'london_grid_202', 'london_grid_203',
    'london_grid_204', 'london_grid_205', 'london_grid_206',
    'london_grid_207', 'london_grid_208', 'london_grid_209',
    'london_grid_210', 'london_grid_211', 'london_grid_212',
    'london_grid_213', 'london_grid_214', 'london_grid_215',
    'london_grid_216', 'london_grid_217', 'london_grid_218',
    'london_grid_219', 'london_grid_220', 'london_grid_221',
    'london_grid_222', 'london_grid_223', 'london_grid_224',
    'london_grid_225', 'london_grid_226', 'london_grid_227',
    'london_grid_228', 'london_grid_229', 'london_grid_230',
    'london_grid_231', 'london_grid_232', 'london_grid_233',
    'london_grid_234', 'london_grid_235', 'london_grid_236',
    'london_grid_237', 'london_grid_238', 'london_grid_239',
    'london_grid_240', 'london_grid_241', 'london_grid_242',
    'london_grid_243', 'london_grid_244', 'london_grid_245',
    'london_grid_246', 'london_grid_247', 'london_grid_248',
    'london_grid_249', 'london_grid_250', 'london_grid_251',
    'london_grid_252', 'london_grid_253', 'london_grid_254',
    'london_grid_255', 'london_grid_256', 'london_grid_257',
    'london_grid_258', 'london_grid_259', 'london_grid_260',
    'london_grid_261', 'london_grid_262', 'london_grid_263',
    'london_grid_264', 'london_grid_265', 'london_grid_266',
    'london_grid_267', 'london_grid_268', 'london_grid_269',
    'london_grid_270', 'london_grid_271', 'london_grid_272',
    'london_grid_273', 'london_grid_274', 'london_grid_275',
    'london_grid_276', 'london_grid_277', 'london_grid_278',
    'london_grid_279', 'london_grid_280', 'london_grid_281',
    'london_grid_282', 'london_grid_283', 'london_grid_284',
    'london_grid_285', 'london_grid_286', 'london_grid_287',
    'london_grid_288', 'london_grid_289', 'london_grid_290',
    'london_grid_291', 'london_grid_292', 'london_grid_293',
    'london_grid_294', 'london_grid_295', 'london_grid_296',
    'london_grid_297', 'london_grid_298', 'london_grid_299',
    'london_grid_300', 'london_grid_301', 'london_grid_302',
    'london_grid_303', 'london_grid_304', 'london_grid_305',
    'london_grid_306', 'london_grid_307', 'london_grid_308',
    'london_grid_309', 'london_grid_310', 'london_grid_311',
    'london_grid_312', 'london_grid_313', 'london_grid_314',
    'london_grid_315', 'london_grid_316', 'london_grid_317',
    'london_grid_318', 'london_grid_319', 'london_grid_320',
    'london_grid_321', 'london_grid_322', 'london_grid_323',
    'london_grid_324', 'london_grid_325', 'london_grid_326',
    'london_grid_327', 'london_grid_328', 'london_grid_329',
    'london_grid_330', 'london_grid_331', 'london_grid_332',
    'london_grid_333', 'london_grid_334', 'london_grid_335',
    'london_grid_336', 'london_grid_337', 'london_grid_338',
    'london_grid_339', 'london_grid_340', 'london_grid_341',
    'london_grid_342', 'london_grid_343', 'london_grid_344',
    'london_grid_345', 'london_grid_346', 'london_grid_347',
    'london_grid_348', 'london_grid_349', 'london_grid_350',
    'london_grid_351', 'london_grid_352', 'london_grid_353',
    'london_grid_354', 'london_grid_355', 'london_grid_356',
    'london_grid_357', 'london_grid_358', 'london_grid_359',
    'london_grid_360', 'london_grid_361', 'london_grid_362',
    'london_grid_363', 'london_grid_364', 'london_grid_365',
    'london_grid_366', 'london_grid_367', 'london_grid_368',
    'london_grid_369', 'london_grid_370', 'london_grid_371',
    'london_grid_372', 'london_grid_373', 'london_grid_374',
    'london_grid_375', 'london_grid_376', 'london_grid_377',
    'london_grid_378', 'london_grid_379', 'london_grid_380',
    'london_grid_381', 'london_grid_382', 'london_grid_383',
    'london_grid_384', 'london_grid_385', 'london_grid_386',
    'london_grid_387', 'london_grid_388', 'london_grid_389',
    'london_grid_390', 'london_grid_391', 'london_grid_392',
    'london_grid_393', 'london_grid_394', 'london_grid_395',
    'london_grid_396', 'london_grid_397', 'london_grid_398',
    'london_grid_399', 'london_grid_400', 'london_grid_401',
    'london_grid_402', 'london_grid_403', 'london_grid_404',
    'london_grid_405', 'london_grid_406', 'london_grid_407',
    'london_grid_408', 'london_grid_409', 'london_grid_410',
    'london_grid_411', 'london_grid_412', 'london_grid_413',
    'london_grid_414', 'london_grid_415', 'london_grid_416',
    'london_grid_417', 'london_grid_418', 'london_grid_419',
    'london_grid_420', 'london_grid_421', 'london_grid_422',
    'london_grid_423', 'london_grid_424', 'london_grid_425',
    'london_grid_426', 'london_grid_427', 'london_grid_428',
    'london_grid_429', 'london_grid_430', 'london_grid_431',
    'london_grid_432', 'london_grid_433', 'london_grid_434',
    'london_grid_435', 'london_grid_436', 'london_grid_437',
    'london_grid_438', 'london_grid_439', 'london_grid_440',
    'london_grid_441', 'london_grid_442', 'london_grid_443',
    'london_grid_444', 'london_grid_445', 'london_grid_446',
    'london_grid_447', 'london_grid_448', 'london_grid_449',
    'london_grid_450', 'london_grid_451', 'london_grid_452',
    'london_grid_453', 'london_grid_454', 'london_grid_455',
    'london_grid_456', 'london_grid_457', 'london_grid_458',
    'london_grid_459', 'london_grid_460', 'london_grid_461',
    'london_grid_462', 'london_grid_463', 'london_grid_464',
    'london_grid_465', 'london_grid_466', 'london_grid_467',
    'london_grid_468', 'london_grid_469', 'london_grid_470',
    'london_grid_471', 'london_grid_472', 'london_grid_473',
    'london_grid_474', 'london_grid_475', 'london_grid_476',
    'london_grid_477', 'london_grid_478', 'london_grid_479',
    'london_grid_480', 'london_grid_481', 'london_grid_482',
    'london_grid_483', 'london_grid_484', 'london_grid_485',
    'london_grid_486', 'london_grid_487', 'london_grid_488',
    'london_grid_489', 'london_grid_490', 'london_grid_491',
    'london_grid_492', 'london_grid_493', 'london_grid_494',
    'london_grid_495', 'london_grid_496', 'london_grid_497',
    'london_grid_498', 'london_grid_499', 'london_grid_500',
    'london_grid_501', 'london_grid_502', 'london_grid_503',
    'london_grid_504', 'london_grid_505', 'london_grid_506',
    'london_grid_507', 'london_grid_508', 'london_grid_509',
    'london_grid_510', 'london_grid_511', 'london_grid_512',
    'london_grid_513', 'london_grid_514', 'london_grid_515',
    'london_grid_516', 'london_grid_517', 'london_grid_518',
    'london_grid_519', 'london_grid_520', 'london_grid_521',
    'london_grid_522', 'london_grid_523', 'london_grid_524',
    'london_grid_525', 'london_grid_526', 'london_grid_527',
    'london_grid_528', 'london_grid_529', 'london_grid_530',
    'london_grid_531', 'london_grid_532', 'london_grid_533',
    'london_grid_534', 'london_grid_535', 'london_grid_536',
    'london_grid_537', 'london_grid_538', 'london_grid_539',
    'london_grid_540', 'london_grid_541', 'london_grid_542',
    'london_grid_543', 'london_grid_544', 'london_grid_545',
    'london_grid_546', 'london_grid_547', 'london_grid_548',
    'london_grid_549', 'london_grid_550', 'london_grid_551',
    'london_grid_552', 'london_grid_553', 'london_grid_554',
    'london_grid_555', 'london_grid_556', 'london_grid_557',
    'london_grid_558', 'london_grid_559', 'london_grid_560',
    'london_grid_561', 'london_grid_562', 'london_grid_563',
    'london_grid_564', 'london_grid_565', 'london_grid_566',
    'london_grid_567', 'london_grid_568', 'london_grid_569',
    'london_grid_570', 'london_grid_571', 'london_grid_572',
    'london_grid_573', 'london_grid_574', 'london_grid_575',
    'london_grid_576', 'london_grid_577', 'london_grid_578',
    'london_grid_579', 'london_grid_580', 'london_grid_581',
    'london_grid_582', 'london_grid_583', 'london_grid_584',
    'london_grid_585', 'london_grid_586', 'london_grid_587',
    'london_grid_588', 'london_grid_589', 'london_grid_590',
    'london_grid_591', 'london_grid_592', 'london_grid_593',
    'london_grid_594', 'london_grid_595', 'london_grid_596',
    'london_grid_597', 'london_grid_598', 'london_grid_599',
    'london_grid_600', 'london_grid_601', 'london_grid_602',
    'london_grid_603', 'london_grid_604', 'london_grid_605',
    'london_grid_606', 'london_grid_607', 'london_grid_608',
    'london_grid_609', 'london_grid_610', 'london_grid_611',
    'london_grid_612', 'london_grid_613', 'london_grid_614',
    'london_grid_615', 'london_grid_616', 'london_grid_617',
    'london_grid_618', 'london_grid_619', 'london_grid_620',
    'london_grid_621', 'london_grid_622', 'london_grid_623',
    'london_grid_624', 'london_grid_625', 'london_grid_626',
    'london_grid_627', 'london_grid_628', 'london_grid_629',
    'london_grid_630', 'london_grid_631', 'london_grid_632',
    'london_grid_633', 'london_grid_634', 'london_grid_635',
    'london_grid_636', 'london_grid_637', 'london_grid_638',
    'london_grid_639', 'london_grid_640', 'london_grid_641',
    'london_grid_642', 'london_grid_643', 'london_grid_644',
    'london_grid_645', 'london_grid_646', 'london_grid_647',
    'london_grid_648', 'london_grid_649', 'london_grid_650',
    'london_grid_651', 'london_grid_652', 'london_grid_653',
    'london_grid_654', 'london_grid_655', 'london_grid_656',
    'london_grid_657', 'london_grid_658', 'london_grid_659',
    'london_grid_660', 'london_grid_661', 'london_grid_662',
    'london_grid_663', 'london_grid_664', 'london_grid_665',
    'london_grid_666', 'london_grid_667', 'london_grid_668',
    'london_grid_669', 'london_grid_670', 'london_grid_671',
    'london_grid_672', 'london_grid_673', 'london_grid_674',
    'london_grid_675', 'london_grid_676', 'london_grid_677',
    'london_grid_678', 'london_grid_679', 'london_grid_680',
    'london_grid_681', 'london_grid_682', 'london_grid_683',
    'london_grid_684', 'london_grid_685', 'london_grid_686',
    'london_grid_687', 'london_grid_688', 'london_grid_689',
    'london_grid_690', 'london_grid_691', 'london_grid_692',
    'london_grid_693', 'london_grid_694', 'london_grid_695',
    'london_grid_696', 'london_grid_697', 'london_grid_698',
    'london_grid_699', 'london_grid_700', 'london_grid_701',
    'london_grid_702', 'london_grid_703', 'london_grid_704',
    'london_grid_705', 'london_grid_706', 'london_grid_707',
    'london_grid_708', 'london_grid_709', 'london_grid_710',
    'london_grid_711', 'london_grid_712', 'london_grid_713',
    'london_grid_714', 'london_grid_715', 'london_grid_716',
    'london_grid_717', 'london_grid_718', 'london_grid_719',
    'london_grid_720', 'london_grid_721', 'london_grid_722',
    'london_grid_723', 'london_grid_724', 'london_grid_725',
    'london_grid_726', 'london_grid_727', 'london_grid_728',
    'london_grid_729', 'london_grid_730', 'london_grid_731',
    'london_grid_732', 'london_grid_733', 'london_grid_734',
    'london_grid_735', 'london_grid_736', 'london_grid_737',
    'london_grid_738', 'london_grid_739', 'london_grid_740',
    'london_grid_741', 'london_grid_742', 'london_grid_743',
    'london_grid_744', 'london_grid_745', 'london_grid_746',
    'london_grid_747', 'london_grid_748', 'london_grid_749',
    'london_grid_750', 'london_grid_751', 'london_grid_752',
    'london_grid_753', 'london_grid_754', 'london_grid_755',
    'london_grid_756', 'london_grid_757', 'london_grid_758',
    'london_grid_759', 'london_grid_760', 'london_grid_761',
    'london_grid_762', 'london_grid_763', 'london_grid_764',
    'london_grid_765', 'london_grid_766', 'london_grid_767',
    'london_grid_768', 'london_grid_769', 'london_grid_770',
    'london_grid_771', 'london_grid_772', 'london_grid_773',
    'london_grid_774', 'london_grid_775', 'london_grid_776',
    'london_grid_777', 'london_grid_778', 'london_grid_779',
    'london_grid_780', 'london_grid_781', 'london_grid_782',
    'london_grid_783', 'london_grid_784', 'london_grid_785',
    'london_grid_786', 'london_grid_787', 'london_grid_788',
    'london_grid_789', 'london_grid_790', 'london_grid_791',
    'london_grid_792', 'london_grid_793', 'london_grid_794',
    'london_grid_795', 'london_grid_796', 'london_grid_797',
    'london_grid_798', 'london_grid_799', 'london_grid_800',
    'london_grid_801', 'london_grid_802', 'london_grid_803',
    'london_grid_804', 'london_grid_805', 'london_grid_806',
    'london_grid_807', 'london_grid_808', 'london_grid_809',
    'london_grid_810', 'london_grid_811', 'london_grid_812',
    'london_grid_813', 'london_grid_814', 'london_grid_815',
    'london_grid_816', 'london_grid_817', 'london_grid_818',
    'london_grid_819', 'london_grid_820', 'london_grid_821',
    'london_grid_822', 'london_grid_823', 'london_grid_824',
    'london_grid_825', 'london_grid_826', 'london_grid_827',
    'london_grid_828', 'london_grid_829', 'london_grid_830',
    'london_grid_831', 'london_grid_832', 'london_grid_833',
    'london_grid_834', 'london_grid_835', 'london_grid_836',
    'london_grid_837', 'london_grid_838', 'london_grid_839',
    'london_grid_840', 'london_grid_841', 'london_grid_842',
    'london_grid_843', 'london_grid_844', 'london_grid_845',
    'london_grid_846', 'london_grid_847', 'london_grid_848',
    'london_grid_849', 'london_grid_850', 'london_grid_851',
    'london_grid_852', 'london_grid_853', 'london_grid_854',
    'london_grid_855', 'london_grid_856', 'london_grid_857',
    'london_grid_858', 'london_grid_859', 'london_grid_860']

'''
dbg_items = 5
if DBG:
    bj_grids = bj_grids[:dbg_items]
    ld_grids = ld_grids[:dbg_items]
    bj_stations = bj_stations[:dbg_items]
    ld_stations = ld_stations[:dbg_items]
'''
