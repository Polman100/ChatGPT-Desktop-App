# openai_costs.py
import requests
import time
import os
from dotenv import load_dotenv

# Wczytaj .env raz na cały moduł
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
load_dotenv("admin_key.env")
api_key = os.getenv("OPENAI_ADMIN_KEY")
if api_key is None:
    raise ValueError("Brak klucza API. Sprawdź plik admin_key.env!")

def get_usage_function(start_date: str, end_date: str = None, verbose: bool = False) -> float:
    """
    Zwraca łączny koszt korzystania z OpenAI API w podanym zakresie dat.
    :param start_date: Początek (format YYYY-MM-DD)
    :param end_date: Koniec (format YYYY-MM-DD), opcjonalnie
    :param verbose: Czy wypisywać dzienne szczegóły
    :return: suma kosztów w USD (float)
    """
    # Zamiana daty w formacie tekstowym na znacznik czasu (sekundy od 1970-01-01)
    start_time = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")))
    end_time = int(time.mktime(time.strptime(end_date, "%Y-%m-%d"))) if end_date else None

    url = "https://api.openai.com/v1/organization/costs"
    params = {
        "start_time": start_time,
        "limit": 180,
        "bucket_width": "1d"
    }
    if end_time:
        params["end_time"] = end_time

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        total_cost = 0.0  # tutaj trzymamy sumę jako float

        # Iterujemy po „koszykach” (bucketach) dziennych
        for bucket in data["data"]:
            # W każdym bucket mogą być różne wyniki (np. różne produkty)
            for result in bucket["results"]:
                # amount["value"] przychodzi najczęściej jako string, np. "0.0123"
                amount_str = result["amount"]["value"]

                # Zamiana stringa na liczbę zmiennoprzecinkową
                try:
                    amount = float(amount_str)
                except (TypeError, ValueError):
                    # Jeśli coś jest nie tak z danymi, lepiej jasno o tym powiedzieć
                    raise ValueError(f"Nie można przekonwertować amount='{amount_str}' na float")

                # Teraz amount jest już float, więc można dodawać do total_cost
                total_cost += amount

                if verbose:
                    date_str = time.strftime('%Y-%m-%d', time.gmtime(bucket['start_time']))
                    print(f"{amount:.4f} USD (dzień: {date_str})")

        return total_cost
    else:
        # W przypadku błędu wypisujemy kod i treść odpowiedzi API
        raise RuntimeError(f"API request failed: {response.status_code} {response.text}")