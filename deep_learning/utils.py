import copy

import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class Dataset(torch.utils.data.Dataset):
    def __init__(self, x, t, location, location_num):
        self.x = np.array(list(reversed(x)))
        self.t = np.array(list(reversed(t)))
        self.location = np.array(list(reversed(location)))
        self.location_num = location_num
        self.size = self.t.size

    def __getitem__(self, idx):
        return (
            torch.from_numpy(self.x[idx]).float(),
            torch.from_numpy(self.t[idx]).float(),
            torch.tensor(self.location[idx]).long(),
        )

    def __len__(self):
        return len(self.x)


class EarlyStopping:
    def __init__(self, patience):
        self.patience = patience
        self.counter = 0
        self.best_value = 1e10
        self.early_stop = False
        self.state_dict = None

    def __call__(self, net, value):
        if value <= self.best_value:
            self.best_value = value
            self.state_dict = copy.deepcopy(net.state_dict())
            self.counter = 0
        else:
            self.counter += 1
        if self.counter == self.patience:
            return True
        else:
            return False


def get_dataloader(X_seq, t_seq, data_src="Japan"):
    if data_src == "Japan":
        df = pd.read_csv("data/raw/Japan.csv").drop("ALL", axis=1)
    elif data_src == "World":
        df = pd.read_csv("data/raw/World.csv")
        df_group = df.groupby("location")

        def func(df):
            location = df["location"].iat[0]
            return pd.DataFrame({"Date": df["date"], location: df["new_cases"]})

        df_group.apply(func)

        df = pd.DataFrame({"Date": []})
        for i in df_group:
            df = pd.merge(df, func(i[1]), on="Date", how="outer")
        df = df.sort_values("Date").reset_index(drop=True)
    elif data_src == "Tokyo":
        df = pd.read_csv("data/raw/Japan.csv")
        df = df[["Date", "Tokyo"]]
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.iloc[:-30]
    df = df.resample("W", on="Date").mean()
    data = np.nan_to_num(df.values, 0.0)
    location2id = {i: j for j, i in enumerate(df.columns)}

    train_data, val_data = train_test_split(data, train_size=0.6, shuffle=False)
    val_data, test_data = train_test_split(val_data, train_size=0.5, shuffle=False)

    min_max_scaler = MinMaxScaler()
    min_max_scaler.fit(train_data)
    train_data = min_max_scaler.transform(train_data)
    val_data = min_max_scaler.transform(val_data)
    test_data = min_max_scaler.transform(test_data)

    train_data = train_data.T
    val_data = val_data.T
    test_data = test_data.T

    train_X = []
    train_t = []
    train_location = []
    val_X = []
    val_t = []
    val_location = []
    test_X = []
    test_t = []
    test_location = []
    for data, X, t, location in [
        [train_data, train_X, train_t, train_location],
        [val_data, val_X, val_t, val_location],
        [test_data, test_X, test_t, test_location],
    ]:
        now_idx = data.shape[1]
        while True:
            if now_idx - X_seq - t_seq < 0:
                break
            X += data[:, now_idx - X_seq - t_seq : now_idx - t_seq].tolist()
            t += data[:, now_idx - t_seq : now_idx].tolist()
            now_idx -= t_seq
            location += list(range(data.shape[0]))

    location_num = len(np.unique(location))
    train_dataset = Dataset(train_X, train_t, train_location, location_num)
    val_dataset = Dataset(val_X, val_t, val_location, location_num)
    test_dataset = Dataset(test_X, test_t, test_location, location_num)
    train_dataloader = torch.utils.data.DataLoader(train_dataset, batch_size=4096, shuffle=False)
    val_dataloader = torch.utils.data.DataLoader(val_dataset, batch_size=4096)
    test_dataloader = torch.utils.data.DataLoader(test_dataset, batch_size=4096)
    return train_dataloader, val_dataloader, test_dataloader, min_max_scaler, location2id
