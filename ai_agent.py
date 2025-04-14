from google import genai
from google.genai import types

from dotenv import load_dotenv
from datetime import datetime
import pytz
import requests
import subprocess
load_dotenv()

#schema objects for a tool
execute_command_schema={
    "name":"execute_command",
    "description":"Execute the given commands and returns dictionary having args,return_code,stdout,stderr. if the command is identified as harmful then the dictionary key return_code = 99999",
    "parameters":{
        "type":"object",
        "properties":{
            "command":{
                "type":"string",
                "description":"The command to execute on Linux machine"
            }
        },
        "required":["command"]
    }
}

get_weather_schema={
    "name":"get_weather",
    "description":"Fetch the weather of given location and return as string",
    "parameters":{
        "type":"object",
            "properties":{
                "location":{
                    "type":"string",
                    "description":"location as in city/villege or any place on earth"
                }
        },
        "required":["location"],
    }
}

get_current_time_schema={
    "name":"get_current_time",
    "description":"get current time based on timezone. returns current time string if valid timezone else return string mentioning Invalid Timezone. timezone is optional if not provided it should fetch the time considering timezone as 'Asia/Kolkata'",
    "parameters":{
        "type":"object",
        "properties":{
            "timezone":{
                "type":"string",
                "description":"timezone to fetch the current time"
            }
        }
    }
}
#functions for tool

def is_command_safe(command: str) -> dict:
    dangerous_patterns = [
        "rm -rf",         # delete
        "mkfs",       # format a drive
        ":(){:|:&};:", # fork bomb
        "shutdown",   # system shutdown
        "reboot",     # system reboot
        "dd if=",     # can be used to wipe disks
        "curl http",  # can be used to pipe remote scripts
        "wget http",
        "chmod 777",  # unsafe permissions
        "chown",      # ownership change
        "kill -9",    # force kill
        ">& /dev/null", # suppress logs
    ]

    command = command.lower().strip()

    return not any(danger in command for danger in dangerous_patterns)

def execute_command(command: str) -> dict:
    if not is_command_safe(command):
        return {
            "args": command,
            "returncode": 99999,
            "stdout": None,
            "stderr": "This command is identified as dangerous and cannot be executed"
        }

    cmd = command
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False,shell=True)
        result = {
            "args": res.args,
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr
        }
    except FileNotFoundError as fnf_error:
        result = {
            "args": cmd,
            "returncode": 127,
            "stdout": None,
            "stderr": f"Command not found: {fnf_error}"
        }
    except Exception as e:
        result = {
            "args": cmd,
            "returncode": 1,
            "stdout": None,
            "stderr": str(e)
        }

    return result

def get_weather(location:str) -> str:

    URL = f"https://wttr.in/{location}?format=%C+%t"
    response = requests.get(URL)

    if response.status_code == 200:
        return f"Weather for {location} is {response.text}"
    else:
        return f"Someething went wrong. Unabl to fetch the weather for {location}"

def get_current_time(timezone:str = "Asia/Kolkata")-> str:
    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz)
        return current_time.strftime('%Y-%m-%d %H:%M:%S %Z%z')
    except pytz.UnknownTimeZoneError:
        return f"Unknown timezone:{timezone}"


client = genai.Client()

system_instructions="""
You are a smart AI Assistant who helps the user to solve the complex problem by providing more context out of it. explain the user with more data about the query.

reformat the query if the query provided by user is not upto mark. like suppose.
1. user asked to provide current time in dubai then you should identify timezone for user and give respective tool call.
2. if user asked to create any file or to execute any command that would potentially create new file or directory if user did not provide any permissions then by default provide 666 permissions. also inform user about the permissions.

"""

tools = types.Tool(function_declarations=[get_weather_schema,execute_command_schema,get_current_time_schema])
config = types.GenerateContentConfig(
    tools=[tools],
    system_instruction=system_instructions
)

chat = client.chats.create(
    model="gemini-2.0-flash",
    config=config
)


while True:
    
    user_query = input(">> ")
    response = chat.send_message(user_query)

    if user_query.lower() == "exit":
        break
    if response.function_calls:
        fn_response_part = []
        for fn in response.function_calls:
            print(fn)
            if fn.name == "get_weather":
                fn_response = get_weather(fn.args['location'])
                #print(fn_response)
                fn_response_part.append(types.Part.from_function_response(
                    name=fn.name,
                    response={"result":fn_response}
                ))
            elif fn.name == "execute_command":
                fn_response = execute_command(fn.args['command'])
                print(fn_response)
                fn_response_part.append(types.Part.from_function_response(
                    name=fn.name,
                    response={"result":fn_response}
                ))
            elif fn.name == "get_current_time":
                if not fn.args:
                    fn_response = get_current_time()
                else:  
                    fn_response = get_current_time(fn.args['timezone'])
                print(fn_response)
                fn_response_part.append(types.Part.from_function_response(
                    name=fn.name,
                    response={"result":fn_response}
                ))
        print(fn_response_part)
        response = chat.send_message(fn_response_part)
        print("🧠 ",response.text)
    else:
        print("🤖 ",response.text)