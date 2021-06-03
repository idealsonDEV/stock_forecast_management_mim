import numpy as np

np.seterr(divide='ignore', invalid='ignore')

def moyenneMobile(arr_data):
    mm4 = np.zeros(16, dtype='float32')
    for i in range(len(mm4)):
        if i in [0,1,14,15]:
            mm4[i] = np.NaN
            continue
        mm4[i] = (arr_data[i-2]/2)+arr_data[i-1]+arr_data[i]+arr_data[i+1]+(arr_data[i+2]/2)
    return mm4/4

def coefSaison2(arr_data):
    coef = np.zeros(4, dtype='float32')
    my = np.zeros(4, dtype='float32')
    my[0] = np.mean([arr_data[0],arr_data[1],arr_data[2],arr_data[3]])
    my[1] = np.mean([arr_data[4],arr_data[5],arr_data[6],arr_data[7]])
    my[2] = np.mean([arr_data[8],arr_data[9],arr_data[10],arr_data[11]])
    my[3] = np.mean([arr_data[12],arr_data[13],arr_data[14],arr_data[15]])
    mt = np.zeros(4, dtype='float32')
    mt[0] = np.mean([arr_data[0],arr_data[4],arr_data[8]])
    mt[1] = np.mean([arr_data[1],arr_data[5],arr_data[9]])
    mt[2] = np.mean([arr_data[2],arr_data[6],arr_data[10]])
    mt[3] = np.mean([arr_data[3],arr_data[7],arr_data[11]])
    mom = np.mean(my)
    coef[0] = mt[0]/mom
    coef[1] = mt[1]/mom
    coef[2] = mt[2]/mom
    coef[3] = mt[3]/mom
    return coef

def coefSaison(rapport):
    temp = np.zeros(4, dtype='float32')
    for i in range(len(rapport)):
        add = rapport[i]
        temp[i%4] += add
    coef = temp/4

    if np.sum(coef) == 4.0:
        return coef
    else:
        m_coe = np.sum(coef)/4
        coef = coef /m_coe
        return coef
    

def dataCorectSaison(arr_data,coef):
    data_off_coef = np.zeros(16, dtype='float32')
    for i in range(len( data_off_coef)):
        div = np.divide(arr_data[i],coef[i%4], out=np.zeros(1, dtype='float32'), where=coef[i%4]!=0)
        data_off_coef[i] = np.nan_to_num(div)
    return data_off_coef

    
def predict(list_data_tr):
    trimes_3_years = np.array([1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],dtype='float32')
    arr_data = np.array(list_data_tr,  dtype='float32')
    mm4 = moyenneMobile(arr_data)
    rapport = np.nan_to_num(arr_data/mm4)
    coef = coefSaison(rapport)
    data_off_coef = dataCorectSaison(arr_data,coef)
    x_bar = np.mean(trimes_3_years)
    y_bar = np.mean(data_off_coef)
    X = trimes_3_years - x_bar
    Y = data_off_coef - y_bar
    XY = X*Y
    X2 = X**2
    a = np.sum(XY)/np.sum(X2)
    b = y_bar - (a*x_bar)
    T17 = a*17 + b
    return np.floor(T17), np.floor(T17* coef[0])

def get_tendency(list_data_tr):
    trimes_3_years = np.array([1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],dtype='float32')
    arr_data = np.array(list_data_tr,  dtype='float32')
    mm4 = moyenneMobile(arr_data)
    rapport = np.nan_to_num(arr_data/mm4)
    coef = coefSaison(rapport)
    data_off_coef = dataCorectSaison(arr_data,coef)
    x_bar = np.mean(trimes_3_years)
    y_bar = np.mean(data_off_coef)
    X = trimes_3_years - x_bar
    Y = data_off_coef - y_bar
    XY = X*Y
    X2 = X**2
    a = np.sum(XY)/np.sum(X2)
    b = y_bar - (a*x_bar)
    return 1, a*1 + b , 16, a*16 +b

def get_moblile_data(list_data_tr):
    trimes_3_years = np.array([1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],dtype='float32')
    arr_data = np.array(list_data_tr,  dtype='float32')
    mm4 = moyenneMobile(arr_data)
    rapport = np.nan_to_num(arr_data/mm4)
    coef = coefSaison(rapport)
    return list(np.floor(dataCorectSaison(arr_data,coef)))

def get_moyenne_mobile(list_data_tr):
    arr_data = np.array(list_data_tr,  dtype='float32')
    mm4 = moyenneMobile(arr_data)
    return list(np.floor(np.nan_to_num(mm4)))

#print predict([3.0, 1.0, 3.0, 0, 0, 0, 0, 2.0, 0, 0, 0, 0, 0, 0, 0, 0])


