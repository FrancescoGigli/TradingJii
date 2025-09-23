import subprocess
import sys
from ansi2html import Ansi2HTMLConverter

filename = "output.html"  # 🔑 sempre lo stesso file

process = subprocess.Popen(
    [sys.executable, "-X", "utf8", "main.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    bufsize=1,
    text=True,
    encoding="utf-8",
    errors="replace"
)

conv = Ansi2HTMLConverter()
with open(filename, "w", encoding="utf-8") as f:
    f.write("<html><body><pre style='font-family: monospace;'>\n")
    for line in process.stdout:
        sys.stdout.write(line)     # mostra a schermo
        sys.stdout.flush()
        f.write(conv.convert(line, full=False))  # scrive nel file
        f.flush()  # 🔑 forza la scrittura immediata sul disco
    f.write("</pre></body></html>\n")

process.wait()

print(f"\n✅ Log salvato in: {filename}")
