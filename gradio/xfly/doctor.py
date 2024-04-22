import requests

conversation_history = []

def doctor_model(message):
    # api_url = 'http://192.168.31.223:8000/v1/chat/completions'
    conversation_history = []
    api_url = 'http://192.168.31.223:8000/v1/chat/completions'
    model_name = 'chatglm2-6b'
    preset_message = "现在请你扮演一名医生，请根据患者的描述回答医疗问题。如果你已经准备好了，请回复我：您好，我是机器人医生，有什么可以帮您。"
    
    if message == "___init___":
        conversation_history.append({"role": "user", "content": preset_message})
    else:
        conversation_history.append({"role": "user", "content": message})
        
    """向大模型API发送请求并获取回答"""
    data = {
        "model": model_name,
        "messages": conversation_history
    }
    print("====1",data)
    response = requests.post(api_url, json=data)
    print("====2",response)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        return f"API错误：{response.status_code}"

