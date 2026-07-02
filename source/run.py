from core.parser import ParserLog

parser = ParserLog()

path = "C:/Users/V1531673/Desktop/data_doing/data"
df_limit,df_data=parser.summary_data(path,mode="rf")
print(df_data)