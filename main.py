import hashlib
import random
from json import JSONDecodeError
from typing import Union, Dict, List, Any
import requests
import time
import datetime
import sys
from urllib.parse import urlencode
from flask import Flask

session = requests.Session()
session.trust_env = False
salt = 'xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs'
app = Flask("genshin-resin")
params = {
    'role_id': '【原神UID】',
    'server': 'cn_gf01',
}
cookies = {
    'account_id': '【米游社UID】',
    'cookie_token': '【抓包获取】',
}

Json = Union[Dict, List, bool, str, int]
Return = Dict[str, Any]

def true_return(data: Json = None, msg: str = '成功') -> Return:
    return {
        'success': True,
        'data': data,
        'msg': msg,
    }

def false_return(msg: str = '出现错误') -> Return:
    return {
        'success': False,
        'msg': msg,
    }

def calc_ds() -> Return:
    t = int(time.time())
    r = random.randint(100000, 200000)
    q = urlencode(params)
    text = f'salt={salt}&t={t}&r={r}&b=&q={q}'
    md5 = hashlib.md5()
    md5.update(text.encode())
    c = md5.hexdigest()
    ds = f'{t},{r},{c}'
    return true_return(ds)

def get_daily() -> Return:
    result = calc_ds()
    if not result['success']:
        return false_return(result['msg'])
    ds = result['data']
    session.headers = {
        'x-rpc-client_type': '5',  # 未变
        'x-rpc-app_version': '2.28.1',
        'Host': 'api-takumi-record.mihoyo.com',
        'DS': ds,
    }
    url = 'https://api-takumi.mihoyo.com/game_record/app/genshin/api/dailyNote'
    response = session.get(url, params=params, cookies=cookies)
    try:
        response = response.json()
    except JSONDecodeError:
        return false_return('JSONDecodeError, response.text: ' + response.text)
    message = response['message']
    if message != 'OK':
        return false_return('message not OK: ' + message)
    current_resin = int(response['data']['current_resin'])
    remain_boss = int(response['data']['remain_resin_discount_num'])
    if mode == 'flask':
        print(f'获取到：当前树脂：{current_resin}，剩余强敌：{remain_boss}')
    return true_return({
        'resin': current_resin,
        'boss': remain_boss,
    })

def cal_time(resin: int, threshold: int) -> Return:
    if resin >= threshold:
        return false_return('resin >= threshold')
    minute = (threshold - resin) * 8
    return true_return(minute)

def get_time(resin: int, threshold: int) -> Return:
    result = cal_time(resin, threshold)
    if not result['success']:
        return false_return(result['msg'])
    now = datetime.datetime.now()
    recovery_time = now + datetime.timedelta(minutes=result['data'])
    recovery_time = recovery_time.strftime('%p%I:%M').replace('AM', '上午').replace('PM', '下午')
    return true_return(f'恢复到%3s树脂：{recovery_time}' % threshold)

def initiative_message(newline: str) -> Return:
    result = get_daily()
    if not result['success']:
        return false_return(result['msg'])
    resin = result['data']['resin']
    boss = result['data']['boss']
    message = f'当前树脂：     {resin}{newline}'
    if boss > 0:
        result = get_time(resin, 30)
        if result['success']:
            message += result['data'] + newline
    else:
        result = get_time(resin, 40)
        if result['success']:
            message += result['data'] + newline
        result = get_time(resin, 60)
        if result['success']:
            message += result['data'] + newline
        result = get_time(resin, 160)
        if result['success']:
            message += result['data'] + newline
    return true_return({
        'msg': message
    })

@app.route('/get', methods=['GET'])
def shortcut() -> str:
    result = initiative_message('<br>')
    if not result['success']:
        return '出现错误：' + result['msg']
    return result['data']['msg']

def send(threshold: int, resin) -> Return:
    send_params = {
        'pushkey': '【pushkey】',
        'text': f'树脂已回复到{threshold}，当前树脂：{resin}'
    }
    send_url = 'https://api2.pushdeer.com/message/push'
    session.get(send_url, params=send_params)
    return true_return()

def calc_threshold(boss: int, remain_boss: int) -> Return:
    if boss > 0:
        threshold = 30
        remain_boss = 2
    elif remain_boss > 0:
        threshold = 60
        remain_boss -= 1
    else:
        threshold = 40
    return true_return({
        'threshold': threshold,
        'remain_boss': remain_boss,
    })

def monitor() -> Return:
    remain_boss = 0
    result = get_daily()
    if not result['success']:
        return false_return(result['msg'])
    resin = result['data']['resin']
    boss = result['data']['boss']
    while True:
        now = datetime.datetime.now()
        print(now.strftime('%Y-%m-%d %H:%M:%S'))
        print('当前树脂：', resin)
        result = calc_threshold(boss, remain_boss)
        if not result['success']:
            return false_return(result['msg'])
        threshold = result['data']['threshold']
        remain_boss = result['data']['remain_boss']
        print('阈值：', threshold)
        deduct_resin = resin  # 扣除后树脂
        result = cal_time(resin, threshold)
        while not result['success']:
            deduct_resin = deduct_resin - threshold
            print('扣除后树脂：', deduct_resin)
            result = cal_time(deduct_resin, threshold)
        minute = result['data']
        recovery_time = now + datetime.timedelta(minutes=minute)
        recovery_time = recovery_time.strftime('%Y-%m-%d %H:%M:%S')
        print(f'程序将在 {minute} 分钟后（{recovery_time}）发送提醒')
        time.sleep(minute * 60)
        result = get_daily()
        if not result['success']:
            return false_return(result['msg'])
        resin = result['data']['resin']
        boss = result['data']['boss']
        result = send(threshold, resin)
        if not result['success']:
            return false_return(result['msg'])
        print('已发送提醒')

def main() -> None:
    if mode == 'monitor':
        result = monitor()
        if not result['success']:
            print('出现错误：' + result['msg'])
    elif mode == 'flask':
        app.run(host='0.0.0.0', port=27018)
    elif mode == 'console':
        result = initiative_message('\n')
        if not result['success']:
            print('出现错误：' + result['msg'])
        print(result['data']['msg'])

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'console'
    main()
