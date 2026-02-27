import os
import shutil
import sys

import pandas

file_sum=sys.argv[0]
output=sys.argv[1]

df=pandas.read_csv(file_sum)

list_file=df['log_path'].dropna().unique()
os.makedirs(output,exist_ok=True)
for file in list_file:
    shutil.copy(file,output)
    print(f"Successfuly copy {file}")