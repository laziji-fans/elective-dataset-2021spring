import torch
import numpy as np
from torchvision.transforms import ToTensor
from PIL import Image
import os
from model import CNN
import preprocess_v3 as preprocess

### begin networking

import getpass
import requests
import time
import io
import random

ELECTIVE_XH = input('学号：')
ELECTIVE_PW = getpass.getpass('密码：')
DELAY_S_MIN = 1.5
DELAY_S_DELTA = 1.5

adapter = requests.adapters.HTTPAdapter(pool_connections=3, pool_maxsize=3, pool_block=True, max_retries=3)
s = requests.Session()
s.mount('http://elective.pku.edu.cn', adapter)
s.mount('https://elective.pku.edu.cn', adapter)

def login():
    print('login')
    res = s.post(
        'https://iaaa.pku.edu.cn/iaaa/oauthlogin.do',
        data={
            'appid': 'syllabus',
            'userName': ELECTIVE_XH,
            'password': ELECTIVE_PW,
            'randCode': '',
            'smsCode': '',
            'otpCode': '',
            'redirUrl': 'http://elective.pku.edu.cn:80/elective2008/ssoLogin.do'
        },
    )
    res.raise_for_status()
    json = res.json()
    assert json['success'], json
    token = json['token']

    res = s.get(
        'https://elective.pku.edu.cn/elective2008/ssoLogin.do',
        params={
            'rand': '%.10f'%random.random(),
            'token': token,
        },
    )
    res.raise_for_status()

def get_captcha():
    res = s.get(
        'https://elective.pku.edu.cn/elective2008/DrawServlet?Rand=114514',
        headers={
            'referer': 'https://elective.pku.edu.cn/elective2008/edu/pku/stu/elective/controller/supplement/SupplyCancel.do',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36',
            #'cookie': ELECTIVE_COOKIE,
        },
        timeout=(3,3),
    )
    res.raise_for_status()
    rawim = res.content
    if not rawim.startswith(b'GIF89a'):
        print(res.text)
        raise RuntimeError('bad captcha')

    return rawim

def check_captcha(captcha):
    res = s.post(
        'https://elective.pku.edu.cn/elective2008/edu/pku/stu/elective/controller/supplement/validate.do',
        headers={
            'referer': 'https://elective.pku.edu.cn/elective2008/edu/pku/stu/elective/controller/supplement/SupplyCancel.do',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36',
            #'cookie': ELECTIVE_COOKIE,
        },
        data={
            'xh': ELECTIVE_XH,
            'validCode': captcha,
        },
        timeout=(3,3),
    )
    res.raise_for_status()
    try:
        json = res.json()
    except Exception as e:
        if '异常刷新' in res.text:
            login()
            return check_captcha(captcha)
        else:
            print(res.text)
            raise

    if json['valid']!='2':
        return False
    else:
        return True

### end networking

from dataset import alphabet

model = CNN()
model.load_state_dict(torch.load('checkpoints/model_29.pth', #'./model_120.pth',
                                 map_location=torch.device('cpu')))
model.eval()

def process(im):
    data = preprocess.gen(im)
    data = torch.stack([ToTensor()(np.expand_dims(c, axis=2)) for c in data], dim=0)
    pred = model(data).view(4, len(alphabet))
    return ''.join(alphabet[i] for i in torch.argmax(pred, dim=1))

def step():
    rawim = get_captcha()
    im = Image.open(io.BytesIO(rawim))
    ans = process(im)
    succ = check_captcha(ans)

    serial = '%d-%d'%(1000*time.time(), random.random()*1000)
    with open('bootstrap_img_%s/%s=%s.gif'%('succ' if succ else 'fail', ans, serial), 'wb') as f:
        f.write(rawim)
    
    return succ

if __name__ == '__main__':
    tot = 0
    totsucc = 0
    login()
    while True:
        try:
            tot += 1
            if step():
                totsucc += 1
            print('acc', totsucc, '/', tot, '=', '%.3f'%(totsucc/tot))
            time.sleep(DELAY_S_MIN + random.random()*DELAY_S_DELTA)
        except Exception as e:
            print('!!!', type(e), e)
            time.sleep(30)
            
