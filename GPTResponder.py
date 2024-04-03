# GPTResponder.py

import asyncio
import openai
from keys import OPENAI_API_KEY
from assistant import Assistant, AssistantParams, Tool, ToolType, Function
from thread import Thread
from prompts import INITIAL_RESPONSE, CUSTOM_SYSTEM_PROMPT, PROBLEM_SOLVING_PROMPT, QUESTION_FINDER, create_problem_prompt#, create_transcription_prompt
import time

openai.api_key = OPENAI_API_KEY

class GPTResponder:
    def __init__(self):
        self.client = openai.AsyncClient(api_key=OPENAI_API_KEY)
        self.insight = None
        self.insight_assistant = None
        self.insight_thread = None
        self.solution_assistant = None
        self.solution_thread = None
        self.response = INITIAL_RESPONSE
        self.response_interval = 2

    async def setup_insight_assistant(self):
        params = AssistantParams(
            name="Insight Assistant",
            # model="gpt-3.5-turbo",
            model="gpt-4-turbo-preview",
            instructions=QUESTION_FINDER,
            tools=[] 
        )
        self.insight_assistant = Assistant(self.client)
        assistant_response = await self.insight_assistant.create_assistant(params)
        self.insight_assistant_id = assistant_response.id
        self.insight_thread = Thread(self.client, self.insight_assistant_id)
        await self.insight_thread.create_thread()
    
    async def setup_solution_assistant(self):
        params = AssistantParams(
            name="Interview Solution Assistant",
            # model="gpt-3.5-turbo",
            model="gpt-4-turbo-preview",
            instructions=PROBLEM_SOLVING_PROMPT,
            tools=[Tool(type=ToolType.code_interpreter)],
        )
        self.solution_assistant = Assistant(self.client)
        assistant_response = await self.solution_assistant.create_assistant(params)
        self.solution_assistant_id = assistant_response.id
        self.solution_thread = Thread(self.client, self.solution_assistant_id)
        await self.solution_thread.create_thread()

    async def insight_from_transcript(self, transcript):
        if not self.insight_thread:
            await self.setup_insight_assistant()
        try:
            await self.insight_thread.create_user_message(transcript)
            await self.insight_thread.run_thread(QUESTION_FINDER)
            messages = await self.insight_thread.get_messages()
            return messages[-1]  # Assuming the last message is the response
        except Exception as e:
            print(f"Error generating response: {e}")
            return ""
    
    def update_response(self, new_text):
        self.response += new_text
        print("Updated Response:", self.response)

    async def solution_from_insight_streaming(self, insight):
        if not self.solution_thread:
            await self.setup_solution_assistant()
        try:
            await self.solution_thread.create_user_message(insight)
            await self.solution_thread.run_streaming_thread(
                callback=self.update_response,
                instructions=PROBLEM_SOLVING_PROMPT,
            )
        except Exception as e:
            print(f"Error generating response with streaming: {e}")

    
    async def respond_to_transcriber(self, transcriber, control_event):
        while True:
            control_event.wait()
            if transcriber.transcript_changed_event.is_set():
                start_time = time.time()

                transcriber.transcript_changed_event.clear()
                transcript_string = transcriber.get_transcript()
                print("Transcript", transcript_string)
                insight = await self.insight_from_transcript(transcript_string)
                if insight != self.insight and insight != "pass":
                    self.insight = insight
                    print("Insight", insight)
                    # self.response = await self.solution_from_insight(insight)
                    self.response = ""
                    await self.solution_from_insight_streaming(insight)
                    print("Response", self.response)

                end_time = time.time()  # Measure end time
                execution_time = end_time - start_time  # Calculate the time it took to execute the function

                remaining_time = self.response_interval - execution_time
                if remaining_time > 0:
                    await asyncio.sleep(remaining_time)
            else:
                await asyncio.sleep(0.3)

    def update_user_prompt(self, prompt):
        self.user_prompt = prompt
        print(self.user_prompt)

    def update_response_interval(self, interval):
        self.response_interval = interval
