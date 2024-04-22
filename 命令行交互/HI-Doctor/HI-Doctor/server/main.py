import pvporcupine
import pyaudio
import numpy as np
import requests
from tts import tts
from stt import stt
from playsound import playsound
import simpleaudio as sa

def ding():
    filename = 'split.wav'  # 指定音频文件路径
    wave_obj = sa.WaveObject.from_wave_file(filename)
    play_obj = wave_obj.play()
    play_obj.wait_done()  # 等待播放完成


def query_model(api_url, model_name, messages):
    """向大模型API发送请求并获取回答"""
    data = {
        "model": model_name,
        "messages": messages
    }
    print(data)
    response = requests.post(api_url, json=data)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        return f"API错误：{response.status_code}"

def doctor(conversation_history):
    api_url = 'http://192.168.31.223:8000/v1/chat/completions'
    model_name = 'chatglm2-6b'
    preset_message = "现在请你扮演一名医生，请根据患者的描述回答医疗问题。如果你已经准备好了，请回复我：您好，我是机器人医生，有什么可以帮您。"

    conversation_history.append({"role": "user", "content": preset_message})
    response = query_model(api_url, model_name, conversation_history)
    # conversation_history.append({"role": "assistant", "content": response})

    return response

def main():
    porcupine = pvporcupine.create(
        access_key='iWWDRjHzeo3dXeEntPnDMf3xmLBz2QOCCbOvdvjP81hwMXrmvavdig==',
        keyword_paths=['hi-doctor_en_windows_v3_0_0/hi-doctor_en_windows_v3_0_0.ppn']
    )

    pa = pyaudio.PyAudio()
    audio_stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=1024
    )

    api_url = 'http://192.168.31.223:8000/v1/chat/completions'
    model_name = 'chatglm2-6b'
    preset_message = "现在请你扮演一名医生，请根据患者的描述回答医疗问题。如果你已经准备好了，请回复我：您好，我是机器人医生，有什么可以帮您。"

    conversation_history = []

    try:
        print("监听唤醒词...")
        while True:
            audio_frame = audio_stream.read(1024)
            if len(audio_frame) / 2 < porcupine.frame_length:
                continue

            pcm = np.frombuffer(audio_frame, dtype=np.int16)[:porcupine.frame_length]
            keyword_index = porcupine.process(pcm)
            #if keyword_index >= 0:
            if True:
                print("检测到唤醒词，开始会话...")
                ding()
                response=doctor(conversation_history)
                # conversation_history.append({"role": "user", "content": preset_message})
                # response = query_model(api_url, model_name, conversation_history)
                conversation_history.append({"role": "assistant", "content": response})
                tts(response)
                print(response)

                while True:
                    print("等待用户输入...")
                    ding()
                    user_input = stt()
                    if user_input.lower() == "退出":
                        tts("好的，如果有问题欢迎再向我提问")
                        break

                    conversation_history.append({"role": "user", "content": user_input})
                    response = query_model(api_url, model_name, conversation_history)
                    conversation_history.append({"role": "assistant", "content": response})
                    tts(response)
                    print(response)

                break
    finally:
        audio_stream.close()
        pa.terminate()
        porcupine.delete()

if __name__ == "__main__":
    main()
