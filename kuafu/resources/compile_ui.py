import PyQt5.uic
import subprocess

# command line or ui compiling
# pyuic5 -x main.ui -o main.py

def compileUIFiles(indir):
  print("Compiling *.ui files...")

  # compile ui files
  PyQt5.uic.compileUiDir(indir, recurse=True)

  # compile qrc files
  print("Compiling *.qrc files...")
  out = subprocess.check_output(["pyrcc5", indir + "resources.qrc"])
  f = open(indir + "resources_rc.py", "wb")
  f.write(out)

  print("Done.")

if __name__ == '__main__':
  compileUIFiles('./kuafu/resources/')
