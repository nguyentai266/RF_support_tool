import glob
import json
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import yaml
from pandas._libs import index

from core.load_config import load_yaml


class ParserLog(object):
	def __init__(self):
		super().__init__()
		self.config=load_yaml()
		self.select_phases=self.config["select_phase"]

	def load_limit(self,filepath,mode=""):
		col_use=["phase","measurement","low_limit","high_limit"]
		df=pd.read_csv(filepath,header=1,usecols=col_use)
		if mode=="audio_sort" or mode == "audio_full" or mode =="":
			sorted_df=df[df["phase"].isin(self.select_phases)].copy()
			df_copy=sorted_df.drop(columns="phase").copy()
			idx = df_copy.columns.get_loc("measurement")
			phase = df_copy["measurement"].str.extract(r'^(.*?)(?=_[\d]+\.?\d*$)')
			freq= df_copy['measurement'].str.extract(r'(\d+\.?\d*)$').astype(float) # lay ra tan so
			df_copy.insert(idx+1,'phase',phase)
			df_copy.insert(idx+2,"freq",freq)
			final=df_copy.drop(columns="measurement")
		elif mode == "rf":
			final=df.copy()
		return final

	def __load_data(self,filepath,mode):
		col_use=["phase","measurement","value"]
		info_log=pd.read_csv(filepath,nrows=0).to_string() #lay dong dau tien cua log
		info_dict={}
		if "dut_id:" in info_log:
			pattern = r'(\w+):\s*([\w\.\-]+)'
			matches=re.findall(pattern,info_log)
			info_dict=dict(matches)
			
		if info_dict:
			dut_id=info_dict.get("dut_id")
			result=info_dict.get("result")
			station_id=info_dict.get("station_id")
			log_id=(re.search(r'(\d{10,15})\.csv$', filepath)).group(1)

			info_df=pd.DataFrame({
				
				"measurement":["dut_id","result","station_id","log_id","log_path"],
				"value":[dut_id,result,station_id,(dut_id+"_"+log_id),filepath]
				})
			df=pd.read_csv(filepath,header=1,usecols=col_use)
			if mode == "" or mode == "audio_sort":
				sort_df=df[df["phase"].isin(self.select_phases)].copy()
				#sort_df['measurement']=sort_df["measurement"].str.extract(r'(\d+\.?\d*)$').astype(float)
				sort_df=sort_df.drop(columns="phase")
				df_combined=pd.concat([info_df,sort_df],ignore_index=True)
				
				df_transpose=df_combined.set_index("measurement").T
			elif mode == "audio_full" or mode == "rf":
				df_full=df.drop(columns="phase").copy()
				#df_full=df.copy()
				df_combined=pd.concat([info_df,df_full],ignore_index=True)
				df_transpose=df_combined.set_index('measurement').T
				
			else:
				return "error"
			
			return df_transpose

	def __process_data(self,filepath,mode):
		try:
			return self.__load_data(filepath,mode)

		except Exception as e:
			print(f"Error: {e}")
			return None

	def summary_data(self,path_dir,mode=""):
		list_file=glob.glob(os.path.join(path_dir,"*.csv"))
		
		if list_file: df_limit=self.load_limit(filepath=list_file[0],mode=mode)
		with ThreadPoolExecutor(max_workers=8) as executor:
			results = list(executor.map(lambda f:self.__process_data(f,mode), list_file))
	
		li = [df for df in results if df is not None]
		if li: df_summary = pd.concat(li, axis=0, ignore_index=True)
		else:  df_summary = pd.DataFrame()
		return df_limit,df_summary		
	
	def copy_file_by_list(self,path_dir,list_file):
		for file in list_file:
			shutil.copy(file,path_dir)
			
	def update_log_files_by_col(self,summary_path,output_path):
		try:
			df_summary = pd.read_csv(summary_path,index_col=0)
			os.makedirs(output_path,exist_ok=True)
			
		except Exception as e:
			print(e)
			
		
		
		target_columns = [col for col in df_summary.columns if col.isdigit()]
		for col in target_columns:
			try:
				
				file_path = df_summary.loc['log_path', col]
			except KeyError: continue

			if not os.path.exists(file_path): 
				
				continue

			with open(file_path, 'r', encoding='utf-8') as f:
				info_file = f.readline().rstrip('\n')
			file_name = os.path.basename(file_path)
	        # đọc log
			df_file = pd.read_csv(file_path, header=1)
	        # Tạo dict map: {item_name: value}
			value_map = df_summary[col].to_dict()
	        # MAP measurement -> value mới
			df_file['value'] = df_file['measurement'].map(value_map).fillna(df_file['value'])
			outfile = os.path.join(output_path, file_name)
			with open(outfile, 'w', encoding='utf-8', newline='') as f:
	    		# ghi dòng info
				f.write(info_file + '\n')
	            # ghi dataframe (header + data)
				df_file.to_csv(f, index=False)
				print(f"Updated: {outfile}")

	def update_log_files_by_row(self, summary_path, output_path):
		try:
			df_summary = pd.read_csv(summary_path)
			os.makedirs(output_path, exist_ok=True)
		except Exception as e:
			print(f"Error: {e}")

		for _, row in df_summary.iterrows():

			file_path = row["log_path"]

			if not os.path.exists(file_path):
				print(f"Missing: {file_path}")
				continue

			# Đọc dòng info đầu
			with open(file_path, "r", encoding="utf-8") as f:
				info_file = f.readline().rstrip("\n")

			# Đọc nội dung log
			df_file = pd.read_csv(file_path, header=1)

			# Tạo map: measurement -> value
			value_map = row.to_dict()

			# Update theo measurement
			df_file["value"] = (
				df_file["measurement"]
				.map(value_map)
				.fillna(df_file["value"])
			)

			# Ghi file mới
			outfile = os.path.join(output_path, os.path.basename(file_path))

			with open(outfile, "w", encoding="utf-8", newline="") as f:
				f.write(info_file + "\n")
				df_file.to_csv(f, index=False)

			print(f"Updated: {outfile}")
			
	def df_phase_freq(self,dataframe):
		if "measurement" in dataframe.columns:
			idx = dataframe.columns.get_loc("measurement")
			phase_data = dataframe["measurement"].str.extract(r'^(.*?)(?=_[\d]+\.?\d*$)')
			freq_data = dataframe["measurement"].str.extract(r'(\d+\.?\d*)$').astype(float)
			dataframe.insert(idx + 1,"phase",phase_data)
			dataframe.insert(idx + 2,"freq",freq_data)
			dataframe["phase"] = dataframe["phase"].fillna(dataframe["measurement"])
			
		df_copy=dataframe.drop(columns=["measurement"]).copy()
		df_copy.to_csv("sdfasdf.csv",index=True)
		return df_copy
	@staticmethod
	def filter_by_dut_station(dataFrame,phase_key,station_id="",dut_id=""):
		raw_df=dataFrame[dataFrame["phase"]==phase_key].copy()
		raw_df=raw_df[raw_df["phase"].isin(["dut_id","station_id",phase_key])]
		raw_df_T=raw_df.T
		df_by_dut=raw_df_T[raw_df_T["phase"]==dut_id]
		return df_by_dut
	



			
		
			
	
	


if __name__=="__main__":
	#file="C:/Users/V1531673/Desktop/RFMS/Audio Basic/data_source/MT5_FVN-E1F3-G01_FATP-AUDIO_BJ25A-01_56100DLCQ00016_GRR_PASS_0-0_1766543317781.csv"
	parser=ParserLog()

	#limit=parser.load_limit(filepath=file)
	#pd.DataFrame.to_csv(limit,"limit.csv")
	'''
	app_path=os.getcwd()
	log_dir=os.path.join(app_path,"data/")
	mode="full"
	df_limit,df_summary=parser.summary_data(log_dir,mode=mode)

	df_summary_transpose=df_summary.T
	df_limit.to_csv("limit.csv",index=False	)
	df_summary_transpose.to_csv("summary.csv",index=True)'''
	#parser.update_log_files("summary.csv","log")
	path="summary.csv"
	data=pd.read_csv(path)
	print(data.columns)
	


	df=parser.df_phase_freq(data,select_phase=['dut_id','station_id',"spk-1_rb"])
	print(df)
	df.to_csv("test.csv",index=False)
	


	
	













		


