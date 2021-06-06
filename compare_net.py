#%%
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import utils
import config
import nets

# url1 ="https://docs.google.com/spreadsheets/d/1Ot0T8_YZ2Q0dORnKEhcUmuYCqZ1y81PIsIAMB7WZE8g/gviz/tq?tqx=out:csv&sheet=%E7%BD%B9%E6%82%A3%E8%80%85_%E6%9D%B1%E4%BA%AC_2020"
# url2 = "https://docs.google.com/spreadsheets/d/1V1eJM1mupE9gJ6_k0q_77nlFoRuwDuBliMLcMdDMC_E/gviz/tq?tqx=out:csv&sheet=%E7%BD%B9%E6%82%A3%E8%80%85_%E6%9D%B1%E4%BA%AC_2021"

# df = pd.concat([pd.read_csv(url1), pd.read_csv(url2)])
# df = df[["公表日", "年代", "性別"]]
# df = df[df["公表日"].notna()]
# start = df["公表日"].iat[0]
# end = df["公表日"].iat[-1]
# index = pd.date_range(start=start, end=end)
# df2 = pd.DataFrame(0, columns=["count"], index=index)
# for date, tmp_df in df.groupby("公表日"):
#     df2.loc[date, "count"] += len(tmp_df)
df = pd.read_csv("./count.csv", parse_dates=True, index_col=0)

#%%
mae_list = []
data = nets.net3.get_data(df)
Net = nets.net3.Net3
net_config = config.net3_config

train_val_test = utils.TrainValTest(data, **config.dataset_config)
utils.run(Net, net_config, train_val_test, config.epoch,
          patience=config.patience)
result = utils.run_repeatedly(Net, net_config, train_val_test, config.epoch,
                              patience=config.patience,
                              repeat_num=config.repeat_num)
mae_list.append(result)

result_df = pd.DataFrame({i: j for i, j in enumerate(mae_list)})
plt.figure()
sns.boxplot(data=result_df)
sns.swarmplot(data=result_df, color="white", size=7, edgecolor="black", linewidth=2)