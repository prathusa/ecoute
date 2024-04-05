# main.py
import threading
from AudioTranscriber import AudioTranscriber
from GPTResponder import GPTResponder
import streamlit as st
import AudioRecorder
import queue
import time
import torch
import sys
import TranscriberModels
import subprocess
import asyncio

FONT_SIZE = 20

def update_transcript_UI(transcriber, textbox):
    transcript_string = transcriber.get_transcript()
    textbox.text_area("Transcript", value=transcript_string, height=200)

def update_response_UI(responder, textbox, update_interval_slider, freeze_state):
    if not freeze_state[0]:
        response = responder.response
        textbox.text_area("Response", value=response, height=200)
        update_interval = update_interval_slider.slider("Update Interval (seconds)", min_value=1, max_value=10, value=2, step=1)
        responder.update_response_interval(update_interval)

def clear_context(transcriber, audio_queue):
    transcriber.clear_transcript_data()
    with audio_queue.mutex:
        audio_queue.queue.clear()

def setup_audio_recorders():
    audio_queue = queue.Queue()
    user_audio_recorder = AudioRecorder.DefaultMicRecorder()
    user_audio_recorder.record_into_queue(audio_queue)
    time.sleep(2)  # Consider optimizing or removing this delay if not necessary
    speaker_audio_recorder = AudioRecorder.DefaultSpeakerRecorder()
    speaker_audio_recorder.record_into_queue(audio_queue)
    return audio_queue, user_audio_recorder, speaker_audio_recorder

def main():
    if 'init_done' not in st.session_state:
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            st.error("ERROR: The ffmpeg library is not installed. Please install ffmpeg and try again.")
            return

        control_event = threading.Event()
        control_event.set()  # Initially allow threads to run

        audio_queue, user_audio_recorder, speaker_audio_recorder = setup_audio_recorders()

        st.session_state['audio_queue'] = audio_queue
        st.session_state['user_audio_recorder'] = user_audio_recorder
        st.session_state['speaker_audio_recorder'] = speaker_audio_recorder
        st.session_state['init_done'] = True
        st.session_state['control_event'] = control_event
    else:
        audio_queue = st.session_state['audio_queue']
        user_audio_recorder = st.session_state['user_audio_recorder']
        speaker_audio_recorder = st.session_state['speaker_audio_recorder']
        control_event = st.session_state['control_event']

    st.set_page_config(page_title="Ecoute", layout="wide")
    st.title("Ecoute")

    col1, col2 = st.columns(2)

    with col1:
        transcript_textbox = st.empty()

    with col2:
        response_textbox = st.empty()
        freeze_state = [False]  # Using list to be able to change its content inside inner functions
        freeze_button = st.button("Freeze")
        update_interval_slider = st.empty()

    model = TranscriberModels.get_model('--api' in sys.argv)
    transcriber = AudioTranscriber(user_audio_recorder.source, speaker_audio_recorder.source, model)

    if 'transcribe' not in st.session_state:
        transcribe = threading.Thread(target=transcriber.transcribe_audio_queue, args=(audio_queue, control_event))
        transcribe.daemon = True
        transcribe.start()
        st.session_state['transcribe'] = transcribe

    def thread_target(transcriber, control_event):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(responder.respond_to_transcriber(transcriber, control_event))
        loop.close()

    responder = GPTResponder()

    if 'respond' not in st.session_state:
        respond = threading.Thread(target=thread_target, args=(transcriber, control_event))
        respond.daemon = True
        respond.start()
        st.session_state['respond'] = respond

    st.write("READY")

    prompt_textbox = st.text_area("User Prompt", height=100)
    send_prompt_button = st.button("Send Prompt")

    def send_prompt_to_responder():
        user_prompt = prompt_textbox  # Retrieve text from prompt_textbox
        responder.update_user_prompt(user_prompt)  # Update the instance variable in GPTResponder

    if send_prompt_button:
        send_prompt_to_responder()

    clear_transcript_button = st.button("Clear Transcript")
    if clear_transcript_button:
        clear_context(transcriber, audio_queue)

    def freeze_unfreeze():
        freeze_state[0] = not freeze_state[0]  # Invert the freeze state

    if freeze_button:
        freeze_unfreeze()

    start_button = st.button("Start")
    if start_button:
        control_event.set()
        user_audio_recorder.start_recording()
        speaker_audio_recorder.start_recording()

    stop_button = st.button("Stop")
    if stop_button:
        control_event.clear()
        user_audio_recorder.stop_recording()
        speaker_audio_recorder.stop_recording()

    update_transcript_UI(transcriber, transcript_textbox)
    update_response_UI(responder, response_textbox, update_interval_slider, freeze_state)

if __name__ == "__main__":
    main()