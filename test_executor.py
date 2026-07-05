from app.automation.command_executor import CommandExecutor

jarvis = CommandExecutor()

while True:
    command = input("Ty: ")

    if command.lower() in ["exit", "koniec", "wyjdź"]:
        print("Jarvis: Kończę pracę.")
        break

    response = jarvis.execute(command)
    print("Jarvis:", response)