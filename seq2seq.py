#!/usr/bin/env python
# coding: utf-8

from keras.layers import Input,LSTM,Dense
from keras.models import Model,load_model
from keras.utils import plot_model
import keras
import pandas as pd
import numpy as np


N_UNITS = 256
BATCH_SIZE = 64
EPOCH =100
NUM_SAMPLES = 10000



data_path = 'data/cmn.txt'
df = pd.read_table(data_path,header=None).iloc[:NUM_SAMPLES,:,]
df.columns=['inputs','targets']

df['targets'] = df['targets'].apply(lambda x: '\t'+x+'\n')

input_texts = df.inputs.values.tolist()
target_texts = df.targets.values.tolist()

input_characters = sorted(list(set(df.inputs.unique().sum())))
target_characters = sorted(list(set(df.targets.unique().sum())))




INUPT_LENGTH = max([len(i) for i in input_texts])
OUTPUT_LENGTH = max([len(i) for i in target_texts])
INPUT_FEATURE_LENGTH = len(input_characters)
OUTPUT_FEATURE_LENGTH = len(target_characters)




encoder_input = np.zeros((NUM_SAMPLES,INUPT_LENGTH,INPUT_FEATURE_LENGTH))
decoder_input = np.zeros((NUM_SAMPLES,OUTPUT_LENGTH,OUTPUT_FEATURE_LENGTH))
decoder_output = np.zeros((NUM_SAMPLES,OUTPUT_LENGTH,OUTPUT_FEATURE_LENGTH))




input_dict = {char:index for index,char in enumerate(input_characters)}
input_dict_reverse = {index:char for index,char in enumerate(input_characters)}
target_dict = {char:index for index,char in enumerate(target_characters)}
target_dict_reverse = {index:char for index,char in enumerate(target_characters)}




for seq_index,seq in enumerate(input_texts):
    for char_index, char in enumerate(seq):
        encoder_input[seq_index,char_index,input_dict[char]] = 1




for seq_index,seq in enumerate(target_texts):
    for char_index,char in enumerate(seq):
        decoder_input[seq_index,char_index,target_dict[char]] = 1.0
        if char_index > 0:
            decoder_output[seq_index,char_index-1,target_dict[char]] = 1.0

def create_model(n_input,n_output,n_units):
    #训练阶段
    #encoder
    encoder_input = Input(shape = (None, n_input))
    #encoder输入维度n_input为每个时间步的输入xt的维度，这里是用来one-hot的英文字符数
    encoder = LSTM(n_units, return_state=True)
    #n_units为LSTM输出维度，return_state设为True返回最后时刻的状态h,c
    _,encoder_h,encoder_c = encoder(encoder_input)#舍弃encoder输出，保留最终状态
    encoder_state = [encoder_h,encoder_c]
    #保留下来encoder的末状态作为decoder的初始状态
    
    #decoder
    decoder_input = Input(shape = (None, n_output))
    #decoder 输入为中文字符数
    decoder = LSTM(n_units,return_sequences=True, return_state=True)
    #训练模型时需要decoder的输出序列来与结果对比优化，故return_sequences也要设为True
    decoder_output, _, _ = decoder(decoder_input,initial_state=encoder_state)
    #在训练阶段只需要用到decoder的输出序列，不需要用最终状态h.c
    decoder_dense = Dense(n_output,activation='softmax')
    decoder_output = decoder_dense(decoder_output)
    #输出序列经过全连接层得到结果
    
    #生成的训练模型
    model = Model([encoder_input,decoder_input],decoder_output)
    #第一个参数为训练模型的输入，包含了encoder和decoder的输入，第二个参数为模型的输出，包含了decoder的输出
    
    #encoder
    encoder_model = Model(encoder_input,encoder_state)
    
    #decoder
    decoder_state_input_h = Input(shape=(n_units,))
    decoder_state_input_c = Input(shape=(n_units,))    
    decoder_state_input = [decoder_state_input_h, decoder_state_input_c]#上个时刻的状态h,c   
    
    decoder_output, decoder_state_h, decoder_state_c = decoder(decoder_input,initial_state=decoder_state_input)
    decoder_state_output = [decoder_state_h, decoder_state_c]#当前时刻得到的状态
    decoder_output = decoder_dense(decoder_output)#当前时刻的输出
    decoder_model = Model([decoder_input]+decoder_state_input,[decoder_output]+decoder_state_output)
    
    return model, encoder_model, decoder_model


model, encoder_model, decoder_model = create_model(INPUT_FEATURE_LENGTH, OUTPUT_FEATURE_LENGTH, N_UNITS)


plot_model(to_file='model.png',model=model,show_shapes=True)
plot_model(to_file='encoder.png',model=encoder_model,show_shapes=True)
plot_model(to_file='decoder.png',model=decoder_model,show_shapes=True)


model.compile(optimizer='rmsprop', loss='categorical_crossentropy')




model.summary()

encoder_model.summary()

decoder_model.summary()


model.fit([encoder_input,decoder_input],decoder_output,batch_size=BATCH_SIZE,epochs=EPOCH,shuffle=True,validation_split=0.2)


model.save('s2s.h5')



def predict_chinese(source,encoder_model, decoder_model, n_steps, features):
    #先通过encoder获得预测输入序列的隐状态
    state = encoder_model.predict(source)
    #第一个字符'\t',为起始标志
    predict_seq = np.zeros((1,1,features))
    predict_seq[0,0,target_dict['\t']] = 1

    output = ''
    #每次循环用上次预测的字符作为输入来预测下一次的字符，直到预测出了终止符
    for i in range(n_steps):#n_steps为句子最大长度
        #给decoder输入上一个时刻的h,c隐状态，以及上一次的预测字符predict_seq
        output_tokens,h,c = decoder_model.predict([predict_seq]+state)
        #注意，这里的yhat为Dense之后输出的结果，因此与h不同
        char_index = np.argmax(output_tokens[0,-1,:])
        char = target_dict_reverse[char_index]
        output += char
        state = [h,c]#本次状态做为下一次的初始状态继续传递
        predict_seq = np.zeros((1,1,features))
        predict_seq[0,0,char_index] = 1
        if char == '\n':#预测到了终止符则停下来
            break
    return output



for i in range(100):
    test = encoder_input[i:i+1,:,:]#i:i+1保持数组是三维
    out = predict_chinese(test,encoder_model,decoder_model,OUTPUT_LENGTH,OUTPUT_FEATURE_LENGTH)
    print(input_texts[i])
    print(out)






