import asyncio

def get_user_input() -> str:
    return input("Please enter your command: ")

async def main_async(user_input: str):
    # Process user input asynchronously
    print(f"Processing: {user_input}")
    # ... your async logic ...

def main():
    user_input = get_user_input()  # Gather input synchronously
    asyncio.run(main_async(user_input))

if __name__ == '__main__':
    main()