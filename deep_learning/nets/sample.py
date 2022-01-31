import pandas as pd
import torch.nn as nn


class Net(nn.Module):
    def __init__(self, hidden_size, num_layers, predict_seq):
        super().__init__()
        self.lstm = nn.LSTM(1, hidden_size, num_layers, batch_first=True)
        self.linear = nn.Linear(hidden_size, predict_seq)

    def forward(self, x):
        x, _ = self.lstm(x)
        y = self.linear(x[:, -1, :])
        return y

    @staticmethod
    def get_data():
        # df = pd.read_csv("./data/count_tokyo.csv", parse_dates=True, index_col=0)
        # data = df.to_numpy(dtype=float)[150:]
        import numpy as np

        data = np.arange(1, 20, dtype=float).reshape(-1, 1)
        normalization_idx = [0]
        return data, normalization_idx

    net_params = [("hidden_size", [1, 2, 4, 8, 16]), ("num_layers", [1, 2])]