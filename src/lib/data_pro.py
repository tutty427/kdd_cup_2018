import pandas as pd
import numpy as np
import datetime as dt
import pickle
from collections import OrderedDict
from lib.define import *

def read_bj_aq():
    bj_aq = pd.read_csv('../input/beijing_aq.csv')
    bj_aq.columns = ['StationId', 'UtcTime', 'PM25', 'PM10', 'NO2', 'CO', 'O3', 'SO2']
    print(len(bj_aq))

    bj_aq1 = pd.read_csv('../input/bj_aq_ex.csv')
    bj_aq1.drop(['id'], axis=1, inplace=True)
    bj_aq1.columns = ['StationId', 'UtcTime', 'PM25', 'PM10', 'NO2', 'CO', 'O3', 'SO2']
    print(len(bj_aq1))

    bj_aq = bj_aq.append(bj_aq1)
    bj_aq.drop_duplicates(subset=['StationId', 'UtcTime'], inplace=True)
    print(len(bj_aq))
    return bj_aq

def read_ld_aq():
    ld_aq = pd.read_csv('../input/london_aq.csv')
    ld_aq.columns = ['StationId', 'UtcTime', 'PM25', 'PM10', 'NO2']
    print(len(ld_aq))

    ld_aq1 = pd.read_csv('../input/ld_aq_ex.csv')
    ld_aq1.drop(['id'], axis=1, inplace=True)
    ld_aq1.columns = ['StationId', 'UtcTime', 'PM25', 'PM10', 'NO2', 'CO', 'O3', 'SO2']
    print(len(ld_aq1))

    ld_aq = ld_aq.append(ld_aq1)
    ld_aq.drop_duplicates(subset=['StationId', 'UtcTime'], inplace=True)
    print(len(ld_aq))
    return ld_aq

#qianmen_aq = read_bj_aq[read_bj_aq['StationId'] == 'qianmen_aq']

def check_stations(df):
    station_list = df.StationId.unique()
    ref_len = len(df[df['StationId'] == station_list[0]])
    print('Reference length: {}'.format(ref_len))
    not_eq_cnt = 0
    for st in station_list:
        st_len = len(df[df['StationId'] == st])
        if st_len != ref_len:
            not_eq_cnt += 1
            print('{} length: {}'.format(st, st_len))

    print('not equal count: {}'.format(not_eq_cnt))


def dt2str(dt, format="%Y-%m-%d %H:%M:%S"):
    return dt.strftime(format)

def dt2pdts(dt):
    str = dt2str(dt)
    ts = pd.Timestamp(str)
    return ts

def build_df1(bj_aq):
    data_dict = {}
    for key in bj_stations:
        data_dict[key] = []
    bj_aq.UtcTime = pd.to_datetime(bj_aq.UtcTime)
    #bj_aq.UtcTime.apply(to_pydt)
    start = dt.datetime(year=2017, month=1, day=1, hour=0)
    end = pd.to_datetime(bj_aq.UtcTime.iloc[-1]).to_pydatetime()
    t = start
    df_cnt = 0
    while t <= end:
        for st in data_dict:
            ts = dt2pdts(t)
            row = bj_aq[(bj_aq.StationId==st) & (bj_aq.UtcTime==ts)]
            if len(row) > 0:
                row_dict = row.to_dict()
            else:
                row_dict = {'StationId': st, 'UtcTime': ts, 'PM25': np.nan, 'PM10': np.nan, 'NO2': np.nan, 'CO': np.nan, 'O3': np.nan, 'SO2': np.nan}
            data_dict[st].append(row_dict)
        df_cnt += 1
        if df_cnt % 100 == 0:
            print(df_cnt)
        t += dt.timedelta(hours=1)

    for st in data_dict:
        data_dict[st] = pd.DataFrame(data_dict)
        print(st, len(data_dict[st]))
    return data_dict

def build_data_dict(df_aq, city='bj'):
    ##Get station list
    #st_list = list(df_aq.StationId.unique())
    ##remove the illegal names
    #for item in st_list:
    #    if type(item) != str:
    #        st_list.remove(item)
    #st_list.sort()
    #print(st_list)
    #print('Station number: {}'.format(len(st_list)))
    if city == 'bj':
        st_list = bj_stations
    else:
        st_list = ld_stations

    data_dict = OrderedDict()
    for key in st_list:
        data_dict[key] = []
    df_aq.UtcTime = pd.to_datetime(df_aq.UtcTime)
    #bj_aq.UtcTime.apply(to_pydt)
    start = dt.datetime(year=2017, month=1, day=1, hour=0)
    end = pd.to_datetime(df_aq.UtcTime.iloc[-1]).to_pydatetime()
    for st in data_dict:
        #st = 'LH0'
        sub_df = df_aq[df_aq.StationId == st]
        old_len = len(sub_df)
        #print('\nBefore insert missing rows: {}, {}'.format(st, len(sub_df)))
        df_cnt = 0
        t = start

        while t <= end:
            ts = dt2pdts(t)
            #row = sub_df[sub_df.UtcTime==ts]
            if df_cnt >= len(sub_df):
                row_dict = {'StationId': st, 'UtcTime': ts, 'PM25': np.nan, 'PM10': np.nan, 'NO2': np.nan, 'CO': np.nan, 'O3': np.nan, 'SO2': np.nan}
                t += dt.timedelta(hours=1)
            else:
                sub_row = sub_df.iloc[df_cnt]
                if ts < sub_row.UtcTime:
                    row_dict = {'StationId': st, 'UtcTime': ts, 'PM25': np.nan, 'PM10': np.nan, 'NO2': np.nan, 'CO': np.nan, 'O3': np.nan, 'SO2': np.nan}
                    t += dt.timedelta(hours=1)
                elif ts == sub_row.UtcTime:
                    row_dict = sub_row.to_dict()
                    t += dt.timedelta(hours=1)
                    df_cnt += 1
                    #if df_cnt % 1000 == 0:
                    #    print(df_cnt)
                else:
                    print('should not run here!')
                    exit()
            data_dict[st].append(row_dict)
        data_dict[st] = pd.DataFrame(data_dict[st])
        #print('After insert missing rows: {}, {}'.format(st, len(data_dict[st])))
        print('\nStation "{}", insert missing rows, {} ==>> {}'.format(st, old_len, len(data_dict[st])))

    return data_dict

def build_bj_st1():
    with open('../input/bj_st_dict.pkl', 'rb') as fp:
        data_dict = pickle.load(fp)

    data_nan_dict = {}
    for st in data_dict:
        data_dict[st] = data_dict[st][['PM25', 'PM10', 'O3', 'CO', 'NO2', 'SO2']]
        data_nan_dict[st] = pd.isnull(data_dict[st])#.astype('uint8')
        #data_nan_dict.columns = ['PM25_NAN', 'PM10_NAN', 'O3_NAN', 'CO_NAN', 'NO2_NAN', 'SO2_NAN']
        #data_dict[st] = pd.concat([data_dict[st], data_nan_dict], axis=1)
    return data_dict, data_nan_dict

def build_bj_st():
    with open('../input/bj_st_dict.pkl', 'rb') as fp:
        data_dict = pickle.load(fp)

    data_list = []
    for st in data_dict:
        data_list.append(data_dict[st][['PM25', 'PM10', 'O3', 'CO', 'NO2', 'SO2']])
    np_data = np.stack(data_list)
    return np_data


#load csv, do some processing, and save to pkl
def load_data():
    #axis0: 0, bj; 1, ld
    #axis1: 0, air quality; 1, meterology
    data = [[], []]

    bj_aq = read_bj_aq()
    #check_stations(bj_aq)
    bj_aq = build_data_dict(bj_aq, city='bj')
    data[0].append(bj_aq)

    ld_aq = read_ld_aq()
    #check_stations(ld_aq)
    ld_aq = build_data_dict(ld_aq, city='ld')
    data[1].append(ld_aq)

    save_dump(data, '../input/data.pkl')
    return data


def batch_gen(indices, build_batch, bb_pars={},
              batch_size=128, shuffle=False, forever=True, drop_last=True):
    data_len = len(indices)
    #indices = np.arange(data_len)

    if shuffle:
        np.random.shuffle(indices)

    while True:
        for k in range(0, data_len-batch_size, batch_size):
            excerpt = indices[k:k + batch_size]
            batch_data = build_batch(excerpt, pars=bb_pars)
            yield batch_data

        if not forever:
            break

        if shuffle:
            np.random.shuffle(indices)

    if not drop_last:
        k += batch_size
        if k < data_len:
            excerpt = indices[k:]
            batch_data = build_batch(excerpt, pars=bb_pars)
            yield batch_data

#city: 0 - Beijing; 1 - London
#type: 0 - station, 1 - grid
class DataBuilder(object):
    def __init__(self, pars):
        #self.data = build_bj_st()
        self.raw_data = load_dump('../input/data.pkl')
        self.st_list = []
        self.st_list.append(bj_stations)
        self.st_list.append(ld_stations)
        self.cal_pos_info()
        self.make_aq_data()

        #todo: need to add other data preprocessing, e.g. 9997, a number which is too big
        self.time_len = self.dynamic_features.shape[1]
        self.n_dynamic_feature = self.dynamic_features.shape[-1]
        self.n_fixed_feature = 3
        self.n_dec_feature = 6
        self.max_encode_len = 240
        self.encode_len = pars['encode_len']
        self.decode_len = 48
        self.val_to_end = pars['val_to_end']
        self.batch_size = pars['batch_size']
        self.build_idxes()
        self.train_bb = batch_gen(self.train_idxes, self.build_batch, bb_pars={'with_targets': True}, batch_size=self.batch_size,
                                  shuffle=True, forever=True, drop_last=True)
        self.val_bb = batch_gen(self.val_idxes, self.build_batch, bb_pars={'with_targets': True}, batch_size=self.batch_size,
                                  shuffle=True, forever=True, drop_last=True)
        self.test_bb = batch_gen(self.test_idxes, self.build_batch, bb_pars={}, batch_size=self.batch_size,
                                shuffle=False, forever=False, drop_last=False)

    def cal_pos_info(self):
        self.pos_list = []
        st_ll = []
        st_ll.append(pd.read_csv('../input/Beijing_AirQuality_Stations_cn.csv'))
        st_ll.append(pd.read_csv('../input/London_AirQuality_Stations.csv'))
        for city in (0, 1):
            self.pos_list.append([])
            for st in self.st_list[city]:
                row = st_ll[city][st_ll[city]['StationId']==st]
                longitude = row['Longitude'].values[0]
                latitude = row['Latitude'].values[0]
                pos = cal_pos((latitude, longitude), origin_list[city])
                #print(st, pos)
                self.pos_list[city].append(pos)

    def make_aq_data(self):
        dynamic_features = []
        fixed_features = []
        for city in (0, 1):
            data_dict = self.raw_data[city][0]
            for k, st in enumerate(data_dict):
                #print(st)
                data_dict[st]['CityId'] = city
                data_dict[st]['X'] = self.pos_list[city][k][0]
                data_dict[st]['Y'] = self.pos_list[city][k][1]
                dynamic_features.append(data_dict[st][['PM25', 'PM10', 'O3', 'CO', 'NO2', 'SO2']])
                fixed_features.append(data_dict[st][['CityId', 'X', 'Y']])
        self.dynamic_features = np.stack(dynamic_features)
        self.dynamic_features_mask = np.isnan(self.dynamic_features).astype(int)
        self.dynamic_features = np.asarray(self.dynamic_features, dtype=np.float32)
        self.dynamic_features = np.nan_to_num(self.dynamic_features)

        self.fixed_features = np.stack(fixed_features)
        self.fixed_features = np.asarray(self.fixed_features, dtype=np.float32)

    def build_idxes(self):
        self.idxes = []
        for s_idx in range(self.dynamic_features.shape[0]):
            for t_idx in range(self.encode_len, self.time_len-self.decode_len):
                self.idxes.append((s_idx, t_idx))

        self.train_idxes = []
        for s_idx in range(self.dynamic_features.shape[0]):
            for t_idx in range(self.encode_len, self.time_len-self.decode_len-self.val_to_end):
                self.train_idxes.append((s_idx, t_idx))

        self.val_idxes = []
        for s_idx in range(self.dynamic_features.shape[0]):
            for t_idx in range(self.time_len-self.val_to_end-self.decode_len, self.time_len-self.decode_len):
                self.val_idxes.append((s_idx, t_idx))

        self.test_idxes = []
        for s_idx in range(48):
            self.test_idxes.append((s_idx, self.time_len))

        pass

    def build_batch(self, idxes, pars={}):
        with_targets = False
        if 'with_targets' in pars:
            with_targets = pars['with_targets']

        batch_size = len(idxes)
        enc_dynamic = np.zeros([batch_size, self.encode_len, self.n_dynamic_feature], dtype=np.float32)
        enc_dynamic_nan = np.zeros_like(enc_dynamic)
        enc_fixed = np.zeros([batch_size, self.encode_len, self.n_fixed_feature], dtype=np.float32)
        y_decode = np.zeros([batch_size, self.decode_len, self.n_dec_feature], dtype=np.float32)
        is_nan_decode = np.zeros_like(y_decode)
        encode_len = np.zeros([batch_size], dtype=np.int32)
        decode_len = np.zeros([batch_size], dtype=np.int32)

        #print('SeqLen = {}'.format(self.past_len))
        for k, sti in enumerate(idxes):
            s_idx = sti[0]
            t_idx = sti[1]
            enc_dynamic[k, :self.encode_len, :] = self.dynamic_features[s_idx, t_idx - self.encode_len:t_idx, :]
            enc_dynamic_nan[k, :self.encode_len, :] = self.dynamic_features_mask[s_idx, t_idx - self.encode_len:t_idx, :]
            encode_len[k] = self.encode_len

            if with_targets:
                y_decode[k, :, :] = self.dynamic_features[s_idx, t_idx:t_idx + self.decode_len, :self.n_dec_feature]
                is_nan_decode[k, :, :] = self.dynamic_features_mask[s_idx, t_idx:t_idx + self.decode_len, :self.n_dec_feature]

        batch = {}
        batch['enc_fixed'] = enc_fixed
        batch['enc_dynamic'] = enc_dynamic
        batch['encode_len'] = encode_len
        batch['y_decode'] = y_decode
        batch['decode_len'] = decode_len
        batch['enc_dynamic_nan'] = enc_dynamic_nan
        batch['is_nan_decode'] = is_nan_decode
        return batch



    def build_batch1(self, idxes, pars={}):
        with_targets = False
        if 'with_targets' in pars:
            with_targets = pars['with_targets']

        #print('SeqLen = {}'.format(self.past_len))
        data_batch = []
        data_batch_mask = []
        target_batch = []
        target_batch_mask = []
        data_len = []
        for sti in idxes:
            s_idx = sti[0]
            t_idx = sti[1]
            data_batch.append(self.dynamic_features[s_idx, t_idx - self.encode_len:t_idx, :])
            data_batch_mask.append(self.dynamic_features_mask[s_idx, t_idx - self.encode_len:t_idx, :])
            data_len.append(self.encode_len)

            if with_targets:
                target_batch.append(self.dynamic_features[s_idx, t_idx:t_idx + self.decode_len, :3])
                target_batch_mask.append(self.dynamic_features_mask[s_idx, t_idx:t_idx + self.decode_len, :3])

        #print(len(data_batch), type(data_batch))
        if with_targets:
            return data_batch, data_batch_mask, target_batch, target_batch_mask
        return data_batch, data_batch_mask, data_len




if __name__ == '__main__':
    '''
    bj_aq = read_bj_aq()
    check_stations(bj_aq)
    build_data_dict(bj_aq)
    '''
    #build_bj_st()
    data_builder = DataBuilder()
    data_builder.build_batch([200,300,400], pars={'with_targets': True})


    #complete_time(data_dict)
    #print(bj_aq.StationId.unique())
    pass