import openai
from keys import OPENAI_API_KEY
from prompts import INITIAL_RESPONSE, CUSTOM_SYSTEM_PROMPT
import time

openai.api_key = OPENAI_API_KEY

class GPTResponder:
    def __init__(self):
        self.response = INITIAL_RESPONSE
        self.response_interval = 2
        self.messages = [{"role": "system", "content": CUSTOM_SYSTEM_PROMPT}, {"role": "user", "content": INITIAL_RESPONSE}]

    def generate_response_from_transcript(self, transcript):
        try:
            response = openai.ChatCompletion.create(
                # model="gpt-4-turbo-preview",
                model="gpt-3.5-turbo",
                messages=self.messages + [{"role": "user", "content": transcript}],
                temperature=0.0,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(e)
            return ''

    def update_user_prompt(self, prompt):
        self.user_prompt = prompt
        self.messages.append({"role": "user", "content": prompt})
        print(self.user_prompt)

    def respond_to_transcriber(self, transcriber, control_event):
        while True:
            control_event.wait()
            if transcriber.transcript_changed_event.is_set():
                start_time = time.time()

                transcriber.transcript_changed_event.clear()
                transcript_string = transcriber.get_transcript()
                response = self.generate_response_from_transcript(transcript_string)
                print("Response", response)

                end_time = time.time()  # Measure end time
                execution_time = end_time - start_time  # Calculate the time it took to execute the function

                if response != '':
                    self.response = response
                    self.messages.append({"role": "assistant", "content": response})

                remaining_time = self.response_interval - execution_time
                if remaining_time > 0:
                    time.sleep(remaining_time)
            else:
                time.sleep(0.3)

    def update_response_interval(self, interval):
        self.response_interval = interval
