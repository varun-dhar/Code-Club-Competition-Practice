'''
Python Runner

This scripts runs the bash scripts and produces output.

The java file's name can contain letters (cap & lower),
numbers, and underscores, but nothing else!
> Asd12_23.java is valid
'''

import re
import os
import subprocess

from subprocess import PIPE, Popen




def validateFiles ():
  '''Checks to see if the required files are in the directory are correct'''
  # These are regular expressions to match for the files
  expectedFiles = ["^[a-zA-Z\d\_]+\.java$",  # Java file
                   "^pyRunner\.py$",
                   "^input\.txt$",        
                   "^expectedOut\.txt$",
                   "^scriptCompile\.sh$",
                   "^scriptRun\.sh$"]
  filesFound = []
  for _ in range(len(expectedFiles)):
    filesFound += [False]

  fileList = os.listdir()

  # First search for expected files
  for fileName in fileList:
    for ind in range(len(expectedFiles)):
      regExpExpected = expectedFiles[ind]

      if re.search(regExpExpected, fileName) != None:
        # Found match
        if filesFound[ind]:
          print("[ERROR] Multiple files match expression: " + regExpExpected)
          exit()
        
        filesFound[ind] = True
        break

      if ind == len(expectedFiles) - 1:
        # There should be NO other files
        print("[WARN] Found unexpected file '" + fileName + "'")
  

  for ind in range(len(filesFound)):
    if not filesFound[ind]:
      print("[ERROR] No file matched expression: " + expectedFiles[ind]) # This is why ind is needed
      exit()



def runJavaFile ():
  '''This actually runs the Java file, calling bash scripts and timing them'''
  # Compilation shouldn't count towards the time limit
  # so it's done seperately
  compilationResults = subprocess.run(["./scriptCompile.sh"], stderr=PIPE, stdout=PIPE)
  if (compilationResults.returncode != 0):
    print("[COMPILATION ERROR]")
    printCompilationError(compilationResults.stderr)
    exit()
  
  # Time delay is done according to this solution (linux specific)
  # https://stackoverflow.com/questions/2387485/limiting-the-time-a-program-runs-in-linux
  cmdString = "timeout --kill-after=1s --signal=1 1s ./scriptRun.sh"
  execResults = subprocess.run(cmdString.split(" "), stderr=PIPE, stdout=PIPE)
  if (execResults.returncode == 124): # Timeout is exit code 124 for some reason \shrug
    printRuntimeError("b'Timeout - Execution exceeded 1 second'")
    exit()
  elif (execResults.returncode != 0):
    printRuntimeError(execResults.stderr)
    exit()



def checkAnswers ():
  '''Checks out.txt against expectedOut.txt, and prints whether or not they match up'''
  # We ignore the first entry because it's empty
  expectedAnswers = open("expectedOut.txt").read().split("[Case]")[1:]

  generatedAnswers = ""
  try:
    generatedAnswers = open("out.txt").read().split("[Case]")[1:]
  except IOError:
    # If out.txt cannot be opened, then they likely submitted a file
    # with submissionMode = false
    printSetupError()
    exit()
  finally:
    pass

  if len(expectedAnswers) != len(generatedAnswers):
    printRuntimeError("b'Mismatch in number of test cases, very likely \\n" + \
                      "that submissionMode = false in the .java file. '")
    exit()

  for ind in range(len(expectedAnswers)):
    expAns = expectedAnswers[ind].split("[Result]")[1]
    genAns = generatedAnswers[ind].split("[Result]")[1]

    if expAns != genAns:
      # The [RESULT] line splits the case from the answer
      case = expectedAnswers[ind].split("[Result]")[0] 
      printWrongAnswer(case, expAns, genAns)
      exit()
  
  printSuccess()







#
# Messages that Users should see
#

def printCompilationError (stderr: str):
  '''subprocess.stderr() produces a weirdly formatter string. This simply makes it easier to print'''
  totalString = str(stderr)
  totalString = totalString[2:-1] # The string starts with b' and ends with a 'to
  totalString = totalString.replace("\\t", "\t")
  for line in totalString.split("\\n"):
    print("[COMPILATION ERROR] " + line)


def printRuntimeError (stderr: str):
  '''Prints out a runtime error as well as the test case that caused it'''
  errorMessage = str(stderr)
  errorMessage = errorMessage[2:-1]
  errorMessage = errorMessage.replace("\\t", "\t")

  testcase = ""
  try:
    # This finds the test case that caused the error
    # It's always going to be the last case written to out.txt
    testCase = open("out.txt") \
                .read() \
                .split("[Case]\n")[-1] \
                .split("\n") # final split incase input is multi-line
  except IOError:
    printSetupError()
    exit()
  finally:
    pass
  
  prefix = "[RUNTIME ERROR] "
  print(prefix + "=== CASE ===")
  print(prefix)
  for line in testCase:
    if line != "":
      print(prefix + line)
  print(prefix)

  print(prefix + "=== ERROR ===")
  print(prefix)
  for line in errorMessage.split("\\n"):
    if line != "":
      print(prefix + line)
  print(prefix)


def printSetupError ():
  '''Prints a message to alert that the file is likely not in submission mode'''
  prefix = "[SETUP ERROR] "
  message = "No out.txt file found. \n"
  print(prefix)
  for line in message.split("\n"):
    print(prefix + line)
  print(prefix)


def printWrongAnswer (case: str, expected: str, submission: str):
  '''Prints out an algorithm error'''
  prefix = "[WRONG ANSWER] "
  print(prefix + "=== CASE ===")
  for line in case.split("\n"):
    print(prefix + line)
  
  print(prefix + "=== EXPECTED ===")
  for line in expected.split("\n"):
    print(prefix + line)

  print(prefix + "=== SUBMISSION ===")
  for line in submission.split("\n"):
    print(prefix + line)


def printSuccess ():
  print("[SUCCESS]")
  print("[SUCCESS] All test passed")
  print("[SUCCESS]")









def main ():
  # Move into the correct directory
  # (All file paths assume working dir is the same dir as this file)
  correctDir = os.path.dirname(os.path.realpath(__file__))
  os.chdir(correctDir)

  validateFiles()
  runJavaFile()
  checkAnswers()


if __name__ == "__main__":
  main()