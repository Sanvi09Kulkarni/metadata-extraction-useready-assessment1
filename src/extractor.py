import os, json, time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from src.prompts import SYSTEM_PROMPT

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# our JSON key -> exact (misspelled) CSV column name
CSV_COLUMNS = {
    "agreement_value": "Aggrement Value",
    "agreement_start_date": "Aggrement Start Date",
    "agreement_end_date": "Aggrement End Date",
    "renewal_notice_days": "Renewal Notice (Days)",
    "party_one": "Party One",
    "party_two": "Party Two",
}


def extract_fields(text, retries=6):
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=f"Agreement text:\n\n{text}",
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
            data = json.loads(response.text)
            return {k: data.get(k) for k in CSV_COLUMNS}
        except Exception as e:
            busy = any(code in str(e) for code in ("503", "429"))
            if busy and attempt < retries - 1:
                time.sleep(10 * (attempt + 1))  # wait 10s, 20s, 30s...
                continue
            raise
