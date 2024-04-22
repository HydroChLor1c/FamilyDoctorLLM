import random
import uuid
from ffmpy3 import FFmpeg
import gradio as gr
import tempfile
from xfly.chatbot import (
    ask_question,
    audio_question,
    answer_question
)

from xfly.doctor import doctor_model
import sys, io, os

def wav2pcm(file):
    inputfile = file
    file_type = file.split('.')[-1]
    outputfile = inputfile.replace(file_type, 'pcm')

    ff = FFmpeg(executable='ffmpeg',
        global_options=['-y'],
        inputs={inputfile: None},
        outputs={outputfile: '-acodec pcm_s16le -f s16le -ac 1 -ar 16000'})
    ff.run()
    return outputfile

def user(user_message, history):
    return "", history + \
        [[user_message, None]]
    
def user_audio(audio, history):
    # 语音转文本，返回
    pcmfile = wav2pcm(audio)
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout
    audio_question(pcmfile)
    # 将标准输出重新设置为原来的标准输出
    sys.stdout = old_stdout
    # 获取标准输出的内容
    response = new_stdout.getvalue()
    return audio, history + \
        [[response, None]]
    
def predict_audio(history):
    # 转文本
    output_text = history[-1][1]
    print(output_text)
    return play_voice(output_text)
    
def play_voice(text):
    # 文本转语音
    print("播放文本:", text)
    temp_dir = tempfile.gettempdir()  # 获取系统临时目录
    filename = os.path.join(temp_dir, f"{uuid.uuid4()}.mp3")
    answer_question(text, filename)
    ok_file = f"{filename}.ok"
    while os.path.exists(ok_file):
        os.remove(ok_file)
        with open(filename, 'rb') as fp:
            #os.remove(filename)

            return fp.read()
        os.remove(filename)


def pre_doctor():
    response = doctor_model("___ init___")
    return [[ None , response]]
    
def doctor(history):
    input_text = history[-1][0]
    response = doctor_model(input_text)
    return history + [[ None , response]]

def pre_role():
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout
    ask_question("___ init___")
    sys.stdout = old_stdout
    response = new_stdout.getvalue()
    return [[ None , response]]

def predict(history):
    input_text = history[-1][0]
    # 创建一个字符串流对象，并将其设置为标准输出
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout
    ask_question(input_text)

    # 将标准输出重新设置为原来的标准输出
    sys.stdout = old_stdout

    # 获取标准输出的内容
    response = new_stdout.getvalue()

    return history + [[ None , response]]

with gr.Blocks() as demo:
    title="讯飞 Chatbot",
    description="输入消息来与 讯飞 Chatbot 进行交互。",
    chatbot = gr.Chatbot()
    with gr.Row():
        with gr.Column(scale=4):
            with gr.Column(scale=1):
                user_input = gr.Textbox(
                    show_label=False,
                    placeholder="Shift + Enter发送消息...",
                    lines=10)

                submitBtn = gr.Button("Submit", variant="primary")

                # 录音功能
                with gr.Row(): 
                    # 得到音频文件地址
                    audio = gr.Audio(sources="microphone", type="filepath")
                    output_audio = gr.Audio(label="Speech Output", autoplay=True)


    params = [user_input, chatbot]
    audio_params = [audio, chatbot]
    # 修改按钮点击事件处理逻辑
    submitBtn.click(
        user,
        params,
        params,
        queue=False).then(
        # 使用 doctor 函数代替 predict，以实现使用 doctor 模型
        doctor,
        chatbot,
        chatbot).then(
        lambda: gr.update(
            interactive=True),
        None,
        [user_input],
        queue=False)

    audio.stop_recording(
        user_audio,
        audio_params,
        audio_params,
        queue=False).then(
        doctor,  # 使用 doctor 函数代替 predict，以实现使用 doctor 模型
        chatbot,
        chatbot).then(
        predict_audio,  # 如果这里涉及到医疗相关的语音输出，可能需要根据输出来调整
        chatbot,
        output_audio)

    # 修改启动时加载模型的调用
    demo.load(pre_doctor, None, chatbot)  # 使用 pre_doctor 函数加载医疗模型的初始化逻辑

demo.launch(server_name='0.0.0.0',server_port=7860)

