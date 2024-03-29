import copy

import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class Dataset(torch.utils.data.Dataset):
    def __init__(self, enc_X, dec_X, t, location, location_num):
        self.enc_X = np.array(list(reversed(enc_X)))
        self.dec_X = np.array(list(reversed(dec_X)))
        self.t = np.array(list(reversed(t)))
        self.location = np.array(list(reversed(location)))
        self.location_num = location_num
        self.size = self.t.size

    def __getitem__(self, idx):
        return (
            torch.from_numpy(self.enc_X[idx]).float(),
            torch.from_numpy(self.dec_X[idx]).float(),
            torch.from_numpy(self.t[idx]).float(),
            torch.tensor(self.location[idx]).long(),
        )

    def __len__(self):
        return len(self.enc_X)


class EarlyStopping:
    def __init__(self, patience):
        self.patience = patience
        self.counter = 0
        self.best_value = 1e10
        self.early_stop = False
        self.best_state_dict = None

    def __call__(self, net, value):
        if value <= self.best_value:
            self.best_value = value
            self.best_state_dict = copy.deepcopy(net.state_dict())
            self.counter = 0
        else:
            self.counter += 1
        if self.counter == self.patience:
            return True
        else:
            return False


def get_dataloader(X_seq, t_seq, use_val, mode, batch_size):
    if mode == "Japan":
        df = pd.read_csv("data/raw/Japan.csv").drop("ALL", axis=1)
    elif mode == "World":
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
    elif mode == "Tokyo":
        df = pd.read_csv("data/raw/Japan.csv")
        df = df[["Date", "Tokyo"]]
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.resample("W", on="Date").mean()
    # df = df.drop("Date", axis=1)
    data = np.nan_to_num(df.values, 0.0)
    location2id = {i: j for j, i in enumerate(df.columns)}

    if use_val:
        train_data, val_data = train_test_split(data, train_size=0.6, shuffle=False)
        val_data, test_data = train_test_split(val_data, train_size=0.5, shuffle=False)
    else:
        train_data, test_data = train_test_split(data, train_size=0.8, shuffle=False)
        val_data = test_data.copy()  # 下のコードの整合性のため
    scaler = StandardScaler()
    scaler.fit(train_data)
    train_data = scaler.transform(train_data)
    val_data = scaler.transform(val_data)
    test_data = scaler.transform(test_data)

    train_data = train_data.T
    val_data = val_data.T
    test_data = test_data.T

    train_enc_X = []
    train_dec_X = []
    train_t = []
    train_location = []
    val_enc_X = []
    val_dec_X = []
    val_t = []
    val_location = []
    test_enc_X = []
    test_dec_X = []
    test_t = []
    test_location = []
    for i, (data, enc_X, dec_X, t, location) in enumerate(
        [
            [train_data, train_enc_X, train_dec_X, train_t, train_location],
            [val_data, val_enc_X, val_dec_X, val_t, val_location],
            [test_data, test_enc_X, test_dec_X, test_t, test_location],
        ]
    ):
        now_idx = data.shape[1]
        while True:
            if now_idx - X_seq - t_seq < 0:
                break
            enc_X += data[:, now_idx - X_seq - t_seq : now_idx - t_seq].tolist()
            if i == 2:
                dec_X += data[:, now_idx - t_seq - 1 : now_idx - t_seq].tolist()
            else:
                dec_X += data[:, now_idx - t_seq - 1 : now_idx - 1].tolist()
            t += data[:, now_idx - t_seq : now_idx].tolist()
            now_idx -= t_seq
            location += list(range(data.shape[0]))

    location_num = len(np.unique(location))
    train_dataset = Dataset(train_enc_X, train_dec_X, train_t, train_location, location_num)
    val_dataset = Dataset(val_enc_X, val_dec_X, val_t, val_location, location_num)
    test_dataset = Dataset(test_enc_X, test_dec_X, test_t, test_location, location_num)
    train_dataloader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_dataloader = torch.utils.data.DataLoader(val_dataset, batch_size=batch_size)
    test_dataloader = torch.utils.data.DataLoader(test_dataset, batch_size=batch_size)
    return train_dataloader, val_dataloader, test_dataloader, scaler, location2id


def inverse_scaler(x, location, location_num, scaler):
    x = x.detach().cpu().numpy()  # [N, T]
    location = location.numpy().repeat(x.shape[-1])  # [N*T]
    x = x.reshape(-1)  # [N*T]
    placeholder = np.zeros([len(x), location_num])  # [N*T, location_num]
    placeholder[range(len(placeholder)), location] = x
    x_inverse = scaler.inverse_transform(placeholder)[range(len(placeholder)), location]  # [N*T]
    return x_inverse
