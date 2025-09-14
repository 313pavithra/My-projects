import requests

def get_weather(city, api_key):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    response = requests.get(url)
    data = response.json()
    return data

def main():
    api_key = "2b6491c06131b53495ab51ccb00c6966"   # 👈 change this
    city = input("Enter city name: ")

    data = get_weather(city, api_key)

    if data.get("cod") != 200:  # ❌ error (like city not found, invalid key, etc.)
        print(f"Error: {data.get('message', 'City not found')}")
    else:  # ✅ success
        print(f"City: {data['name']}")
        print(f"Temperature: {data['main']['temp']} °C")
        print(f"Weather: {data['weather'][0]['description'].title()}")
        print(f"Humidity: {data['main']['humidity']}%")
        print(f"Wind Speed: {data['wind']['speed']} m/s")

if __name__ == "__main__":
    main()
