import _thread as thread
import base64
import datetime
import hashlib
import hmac
import json
import pickle
import time
from urllib.parse import urlparse
import ssl
import sys, os
import io
import csv
import uuid
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
# websocket-client
import websocket


STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识

Text_Content = ""  # 语音合成默认内容
Audio_Path = '/tmp/answer.mp3'

class Ws_Param(object):
    # 初始化
    def __init__(self, APPID, APIKey, APISecret, gpt_url):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.host = urlparse(gpt_url).netloc
        self.path = urlparse(gpt_url).path
        self.gpt_url = gpt_url
        # 公共参数(common)
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数(business)，更多个性化参数可在官网查看
        self.TextArgs = {"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vinfo":1,"vad_eos":10000}
        self.AudioArgs = {"aue": "lame", "sfl": 1, "auf": "audio/L16;rate=16000", "vcn": "xiaoyan", "tte": "utf8"}
        
    # 生成url
    def create_url(self):
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + self.host + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + self.path + " HTTP/1.1"

        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()

        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'

        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": self.host
        }
        # 拼接鉴权参数，生成url
        url = self.gpt_url + '?' + urlencode(v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        return url


# 收到websocket错误的处理
def on_error(ws, error):
    print("### error:", error)


# 收到websocket关闭的处理
def on_close(ws, status_code, reason):
    print("")


# 收到websocket连接建立的处理
def on_open(ws):
    if ws.type == "msg":
        thread.start_new_thread(run, (ws,))
    if ws.type == "audio":
        thread.start_new_thread(runa2t, (ws,))
    if ws.type == "text":
        thread.start_new_thread(runt2a, (ws,))

# msg
def run(ws, *args):
    data = json.dumps(gen_params(appid=ws.appid, question=ws.question))
    ws.send(data)

# a2t
def runa2t(ws, *args):
    frameSize = 8000  # 每一帧的音频大小
    intervel = 0.02  # 发送音频间隔(单位:s)
    status = STATUS_FIRST_FRAME  # 音频的状态信息，标识音频是第一帧，还是中间帧、最后一帧

    # print("===",ws.audio)
    with open(ws.audio, "rb") as fp:
        while True:
            buf = fp.read(frameSize)
            # print("======",buf)
            # 文件结束
            if not buf:
                status = STATUS_LAST_FRAME
            # 第一帧处理
            # 发送第一帧音频，带business 参数
            # appid 必须带上，只需第一帧发送
            if status == STATUS_FIRST_FRAME:

                d = {"common": wsParam.CommonArgs,
                    "business": wsParam.TextArgs,
                    "data": {"status": 0, "format": "audio/L16;rate=16000",
                            "audio": str(base64.b64encode(buf), 'utf-8'),
                            "encoding": "raw"}}
                d = json.dumps(d)
                ws.send(d)
                status = STATUS_CONTINUE_FRAME
            # 中间帧处理
            elif status == STATUS_CONTINUE_FRAME:
                d = {"data": {"status": 1, "format": "audio/L16;rate=16000",
                            "audio": str(base64.b64encode(buf), 'utf-8'),
                            "encoding": "raw"}}
                ws.send(json.dumps(d))
            # 最后一帧处理
            elif status == STATUS_LAST_FRAME:
                d = {"data": {"status": 2, "format": "audio/L16;rate=16000",
                            "audio": str(base64.b64encode(buf), 'utf-8'),
                            "encoding": "raw"}}
                ws.send(json.dumps(d))
                time.sleep(1)
                break
            # 模拟音频采样间隔
            time.sleep(intervel)
    # ws.close()
    
# t2a
def runt2a(ws, *args):
    global Audio_Path,wsParam
    d = {"common": wsParam.CommonArgs,
        "business": wsParam.AudioArgs,
        "data": ws.text,
        }
    d = json.dumps(d)
    # print("------>开始发送文本数据")
    ws.send(d)
    if os.path.exists(Audio_Path):
        os.remove(Audio_Path)

# 收到websocket消息的处理
def on_message(ws, message):
    global Text_Content, Audio_Path
    # print(message)
    data = json.loads(message)
    if ws.type == "msg":
        code = data['header']['code']
    else:
        code = data["code"]
        
    if code != 0:
        print(f'请求错误: {code}, {data}')
        ws.close()
    else:
        if ws.type == "msg":
            choices = data["payload"]["choices"]
            status = choices["status"]
            content = choices["text"][0]["content"]
            print(content, end='')
            if status == 2:
                ws.close()
        if ws.type == "audio":
            status = data["data"]["status"]
            data = json.loads(message)["data"]["result"]["ws"]
            result = ""
            for i in data:
                for w in i["cw"]:
                    result += w["w"]
            Text_Content+=result
            if status == 2:
                print(Text_Content, end='')
                ws.close()
            
        if ws.type == "text":
            message =json.loads(message)
            code = message["code"]
            sid = message["sid"]
            audio = message["data"]["audio"]
            audio = base64.b64decode(audio)
            status = message["data"]["status"]
            # print(message)
            if status == 2:
                print("文字转语音完毕!")
                ws.close()
            if code != 0:
                errMsg = message["message"]
                print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))
            else:
                # print("====",Audio_Path)
                with open(Audio_Path, 'ab') as f:
                    f.write(audio)
                
                with open(f"{Audio_Path}.ok", 'ab') as f:
                    f.write("")
                    
def gen_params(appid, question):
    """
    通过appid和用户的提问来生成请参数
    """
    data = {
        "header": {
            "app_id": appid,
            "uid": "1234"
        },
        "parameter": {
            "chat": {
                "domain": "general",
                "random_threshold": 0.5,
                "max_tokens": 2048,
                "auditing": "default"
            }
        },
        "payload": {
            "message": {
                "text": [
                    {"role": "user", "content": question}
                ]
            }
        }
    }
    return data


def main(gpt_url, type, question):
    global wsParam, Text_Content, Audio_Path
    appid="c62e4d22"
    api_secret="NjFlODU3ZmY5ZDg1MzhiZDFlMzM3M2Iy"
    api_key="9cc1578d25d052eead294a7ddde538e6"
    # gpt_url="ws://spark-api.xf-yun.com/v1.1/chat"
    wsParam = Ws_Param(appid, api_key, api_secret, gpt_url)
    websocket.enableTrace(False)
    wsUrl = wsParam.create_url()
    if type == "msg":
        ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open)
        ws.question = question
    if type == "audio":
        ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open)
        ws.audio = question
    if type == "text":
        ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open)
        ws.text = {"status": 2, "text": str(base64.b64encode(question.encode('utf-8')), "UTF8")}
    ws.appid = appid
    ws.type = type
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    return Text_Content

def ask_question(question):
    if question == "___ init___":
        question="现在请你扮演一名医生，请根据患者的描述回答医疗问题。如果你已经准备好了，请回复我：您好，我是机器人医生，有什么可以帮您。"
    main(gpt_url="ws://spark-api.xf-yun.com/v1.1/chat",type="msg", question=question )

def audio_question(question):
    global Text_Content
    Text_Content = ""    
    main(gpt_url="wss://ws-api.xfyun.cn/v2/iat",type="audio", question=question )
    
def answer_question(question, tmpfile):
    global Audio_Path
    Audio_Path = tmpfile
    # if(os.path.exists('/tmp/answer.mp3.ok')):
    #      os.remove('/tmp/answer.mp3.ok')
    main(gpt_url="wss://tts-api.xfyun.cn/v2/tts",type="text", question=question )

def startSparkOne(question):
    ask_question(question)
