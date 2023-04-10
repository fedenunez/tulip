#!/usr/bin/python3
import openai
import argparse
import sys
import os
import math
from . import tulplogger
from . import tulpconfig
from . import version

log = tulplogger.Logger()
config = tulpconfig.TulipConfig()

def run():

    log.info(f"Running tulp v{version.VERSION}.")
    openai_key = config.openai_api_key
    if not openai_key:
        log.error(f'OpenAI API key not found. Please set the TULP_OPENAI_API_KEY environment variable or add it to {tulpconfig.CONFIG_FILE}')
        sys.exit(1)

    openai.api_key = openai_key
    prev_context=None


    # Define command line arguments
    parser = argparse.ArgumentParser(description="A command line interface for the OpenAI GPT language model")
    parser.add_argument("prompt", nargs="*", help="User prompt to send to the language model", type=str)

    # Parse command line arguments
    args = parser.parse_args()

    # If input is available on stdin, read it
    if not sys.stdin.isatty():
        input_text = sys.stdin.read().strip()
    else:
        input_text = ""

    # If prompt is provided as argument, use it to construct the input text
    if args.prompt:
        prompt = " ".join(args.prompt)




    # If prompt is not provided and no input is available on stdin, prompt the user for input
    instructions=None
    if not args.prompt and not input_text:
        input_text = input("Enter your request: ").strip()
    elif args.prompt and not input_text:
        input_text = prompt
    elif not args.prompt and input_text:
        instructions = "Summarize the input"
    elif args.prompt and input_text:
        instructions = prompt




    instructionFunction=None
    if instructions:
        from . import filteringPrompt
        instructionFunction=filteringPrompt.getBaseMessages
    else:
        from . import requestPrompt
        instructionFunction=requestPrompt.getBaseMessages

    user_messages=[]
    # Split input text into chunks to fit within max token window
    max_chars = config.max_chars  # Maximum number of chars that we will send to GPT
    if len(input_text) > max_chars:
        log.warning(f"Warning: input is to big, we will split processing in chunks of less than {max_chars}. You may use the TULP_MAX_CHARS env variable to control the size of the processing chunk size.")
    input_lines = input_text.splitlines()
    # try to split it in lines or max_size
    compressed_lines = [""]

    for iline in input_lines:
        compresed_index = len(compressed_lines) - 1
        clen = len(compressed_lines[compresed_index]) 
        if clen + len(iline) < max_chars:
            compressed_lines[compresed_index] += iline + "\n"
        else:
            if clen != 0:
                if (len(iline) < max_chars):
                    compressed_lines.append(iline + "\n")
                else:
                    for i in range(0,math.floor(len(iline)/max_chars)+1):
                        input_chunk = iline[i*max_chars:(i+1)*max_chars] 
                        compressed_lines.append(input_chunk)
                    compressed_lines[compresed_index] += "\n"

    for line in compressed_lines:
         user_messages.append( {"role": "user", "content": line})



    for i in range(0,len(user_messages)):
        log.info(f"PROCESSING {i+1} of {len(user_messages)}:")
        response_text = ""
        message = user_messages[i]
        if message:
            request = instructionFunction(instructions, len(user_messages), i+1, prev_context)
            if True:
                request.append(message)
                response = openai.ChatCompletion.create(
                    model=config.model,
                    messages=request,
                    temperature=0
                )
                for req in request:
                    log.debug(f"REQ: {req}")
                log.debug(f"ANS: {response}")
                response_text += response.choices[0].message.content
            else:
                response_text += f"(#output)\nsimulated request"



        lines = response_text.splitlines()
        valid_blocks=["(#output)","(#error)","(#context)"]
        blocks_dict={}

        # parse blocks:
        parsingBlock=None
        for line in lines:
            if (line in valid_blocks):
                parsingBlock=line
                blocks_dict[parsingBlock]=""

            else:
                if parsingBlock:
                    blocks_dict[parsingBlock] += line + "\n"
                else:
                    log.error(f"Unknown error while processing: output before quotes?, try a different input: {line} - {parsingBlock}")
                    log.error(response_text)
                    sys.exit(2)


        if "(#error)" in blocks_dict:
            log.error("Error: Couldn't process your request:")
            log.error(blocks_dict["(#error)"])
            sys.exit(1)
        elif "(#output)" in blocks_dict:
            print(blocks_dict["(#output)"])
            if "(#context)" in blocks_dict:
                prev_context = blocks_dict["(#context)"]
            else:
                prev_context = None
        else:
            log.error("Unknown error while processing, try with a different request, model response:")
            log.error(response_text)
            sys.exit(2)

if __name__ == "__main__":
    run()