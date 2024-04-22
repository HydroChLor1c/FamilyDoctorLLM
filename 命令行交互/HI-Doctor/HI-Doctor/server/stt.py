import websocket
import datetime
import hashlib
import base64
import hmac
import json
from urllib.parse import urlencode
import ssl
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import pyaudio
import threading
import time

# 设置您的 APPID、APISecret 和 APIKey
APPID = 'c62e4d22'
APISecret = 'NjFlODU3ZmY5ZDg1MzhiZDFlMzM3M2Iy'
APIKey = '9cc1578d25d052eead294a7ddde538e6'

STATUS_FIRST_FRAME = 0
STATUS_CONTINUE_FRAME = 1
STATUS_LAST_FRAME = 2


class Ws_Param(object):
    # 初始化
    def __init__(self, APPID, APIKey, APISecret):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret

        self.CommonArgs = {"app_id": self.APPID}
        self.BusinessArgs = {"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vinfo": 1, "vad_eos": 10000}

    # 生成url
    def create_url(self):
        url = 'wss://ws-api.xfyun.cn/v2/iat'
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        url = url + '?' + urlencode(v)
        return url


def stt():
    global result
    wsParam = Ws_Param(APPID, APIKey, APISecret)
    result = None
    done_event = threading.Event()

    def on_message(ws, message):
        global result
        try:
            code = json.loads(message)["code"]
            sid = json.loads(message)["sid"]
            if code != 0:
                errMsg = json.loads(message)["message"]
                print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))
            else:
                data = json.loads(message)["data"]["result"]["ws"]

                result = ""
                for i in data:
                    for w in i["cw"]:
                        result += w["w"]
                        print("识别结果:", result)
                        done_event.set() # 收到识别结果后设置事件
        except Exception as e:
                        print("receive msg, but parse exception:", e)
        done_event.set()  # 接收到完整结果后设置事件

    def on_error(ws, error):
        print("### error:", error)
        done_event.set()  # 发生错误时设置事件

    def on_close(ws, close_status_code, close_msg):
        print("### closed ###")
        done_event.set()  # 连接关闭时设置事件

    def on_open(ws):
        def run(*args):
            frame_size = 8000  # 每一帧的音频大小
            interval = 0.04  # 发送音频间隔(单位:s)
            status = STATUS_FIRST_FRAME

            # 设置麦克风采集参数
            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=frame_size)

            try:
                while True:
                    buf = stream.read(frame_size)
                    if status == STATUS_FIRST_FRAME:
                        d = {"common": wsParam.CommonArgs,
                             "business": wsParam.BusinessArgs,
                             "data": {"status": 0, "format": "audio/L16;rate=16000",
                                      "audio": str(base64.b64encode(buf), 'utf-8'), "encoding": "raw"}}
                        ws.send(json.dumps(d))
                        status = STATUS_CONTINUE_FRAME
                    elif status == STATUS_CONTINUE_FRAME:
                        d = {"data": {"status": 1, "format": "audio/L16;rate=16000",
                                      "audio": str(base64.b64encode(buf), 'utf-8'), "encoding": "raw"}}
                        ws.send(json.dumps(d))
                    else:
                        break

                    time.sleep(interval)

                    if done_event.is_set():  # 检查是否已收到识别结果
                        break

            finally:
                stream.stop_stream()
                stream.close()
                p.terminate()
                # 发送结束标志
                d = {"data": {"status": 2, "format": "audio/L16;rate=16000",
                              "audio": str(base64.b64encode(b''), 'utf-8'), "encoding": "raw"}}
                ws.send(json.dumps(d))

        threading.Thread(target=run).start()

    # 建立 WebSocket 连接
    wsUrl = wsParam.create_url()
    ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.on_open = on_open

    ws_thread = threading.Thread(target=ws.run_forever, kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}})
    ws_thread.start()
    done_event.wait()  # 等待识别完成
    ws.close()
    ws_thread.join()

    done_event.wait()  # 等待直到识别完成
    ws.close()
    return result  # 返回识别结果

if __name__ == '__main__':
    res = stt()
    print(res)