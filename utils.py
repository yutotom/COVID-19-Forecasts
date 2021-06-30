import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
if "get_ipython" in globals():
    from tqdm.notebook import tqdm
else:
    from tqdm import tqdm
import torch
import torch.nn as nn
import torch.nn.functional as F
sns.set(font="IPAexGothic")

class Dataset(torch.utils.data.Dataset):
    def __init__(self, data, seq):
        self.seq = seq
        self.data = torch.from_numpy(data).float()

    def __getitem__(self, idx):
        return self.data[idx:idx + self.seq], self.data[idx + self.seq, [0]]

    def __len__(self):
        return len(self.data) - self.seq

    def get_label(self):
        return self.data[:, 0].numpy()

    def get_feature(self, idx):
        return self.data[idx + self.seq, 1:].numpy()

class TrainValTest:
    def __init__(self, data, normalization_idx):
        self.seq = 30
        self.batch_size = 10000
        data = data.copy()
        val_test_len = 30 + self.seq
        train_data = data[:-2*val_test_len]
        val_data = data[-2*val_test_len:-val_test_len]
        test_data = data[-val_test_len:]

        self.normalization_idx = normalization_idx
        self.mean = np.mean(train_data[:, normalization_idx], axis=0)
        self.std = np.std(train_data[:, normalization_idx], axis=0)
        train_data[:, normalization_idx] = (train_data[:, normalization_idx] - self.mean)/self.std
        val_data[:, normalization_idx] = (val_data[:, normalization_idx] - self.mean)/self.std
        test_data[:, normalization_idx] = (test_data[:, normalization_idx] - self.mean)/self.std

        train_dataset = Dataset(train_data, self.seq)
        val_dataset = Dataset(val_data, self.seq)
        test_dataset = Dataset(test_data, self.seq)
        self.dataset_dict = {"train": train_dataset, "val": val_dataset, "test": test_dataset}

        train_dataloader = torch.utils.data.DataLoader(train_dataset, batch_size=self.batch_size)
        val_dataloader = torch.utils.data.DataLoader(val_dataset, batch_size=self.batch_size)
        test_dataloader = torch.utils.data.DataLoader(test_dataset, batch_size=self.batch_size)
        self.dataloader_dict = {"train": train_dataloader, "val": val_dataloader, "test": test_dataloader}

    def inverse_standard(self, data):
        return data*self.std[0] + self.mean[0]

class EarlyStopping:
    def __init__(self, patience):
        self.patience = patience
        self.counter = 0
        self.best_score = 1e10
        self.early_stop = False
        self.state_dict = None

    def __call__(self, net, score):
        if score <= self.best_score:
            self.best_score = score
            self.state_dict = net.state_dict()
            self.counter = 0
        else:
            self.counter += 1
        if self.counter == self.patience:
            return True
        else:
            return False

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(DEVICE)

def run(Net, net_name, net_config, train_val_test, epoch, lr=0.001, use_best=True, plot=True, log=True, patience=-1):
    dataloader_dict = train_val_test.dataloader_dict

    net = Net(**net_config)
    optimizer = torch.optim.Adam(net.parameters(), lr=lr)
    criterion = nn.MSELoss()
    result_dict = {"train_loss": [], "train_mae": [],
                   "val_loss": [], "val_mae": []}
    best_dict = {"mae_loss": 1e10, "state_dict": None, "epoch": 0}

    show_progress = epoch // 100
    break_flag = False
    for i in tqdm(range(epoch), leave=log):
        for phase in ["train", "val"]:
            dataloader = dataloader_dict[phase]
            if phase == "train":
                net.train()
            else:
                net.eval()
            epoch_loss = 0
            epoch_mae = 0
            with torch.set_grad_enabled(phase == "train"):
                for inputs, label in dataloader:
                    inputs = inputs.to(DEVICE)
                    label = label.to(DEVICE)
                    optimizer.zero_grad()
                    outputs = net(inputs)
                    loss = torch.sqrt(criterion(outputs, label))
                    if phase == "train":
                        loss.backward()
                        optimizer.step()
                    epoch_loss += loss.item()*inputs.size(0)
                    epoch_mae += F.l1_loss(train_val_test.inverse_standard(outputs),
                        train_val_test.inverse_standard(label), reduction="sum").item()
            data_len = len(dataloader.dataset)
            epoch_loss /= data_len
            epoch_mae /= data_len
            if i % show_progress == 0 and log:
                tqdm.write(f"{i}_{phase}_epoch_loss: {epoch_loss}")
                tqdm.write(f"{i}_{phase}_epoch_mae: {epoch_mae}")
                if phase == "val":
                    tqdm.write("-"*20)
            result_dict[phase+"_loss"].append(epoch_loss)
            result_dict[phase+"_mae"].append(epoch_mae)
            if phase == "val":
                if epoch_mae < best_dict["mae_loss"]:
                    best_dict["mae_loss"] = epoch_mae
                    best_dict["state_dict"] = net.state_dict()
                    best_dict["epoch"] = i + 1
                if (i + 1) - best_dict["epoch"] == patience:
                    break_flag = True
        if break_flag:
            break

    if plot:
        plt.figure(figsize=(12, 8))
        x = np.arange(len(result_dict["train_loss"]))
        sns.lineplot(x=x, y=result_dict["train_loss"], linewidth=4, label="train_loss")
        sns.lineplot(x=x, y=result_dict["val_loss"], linewidth=4, label="val_loss")
        plt.title("rmse")
        plt.legend(fontsize=16)
        plt.savefig(f"./result_img/{net_name}_rmse.png")
        plt.figure(figsize=(12, 8))
        sns.lineplot(x=x, y=result_dict["train_mae"], linewidth=4, label="train_mae")
        sns.lineplot(x=x, y=result_dict["val_mae"], linewidth=4, label="val_mae")
        plt.title("mae")
        plt.legend(fontsize=16)
        plt.savefig(f"./result_img/{net_name}_mae.png")

    tqdm.write("best_epoch: "+str(best_dict["epoch"]))
    if use_best:
        net.load_state_dict(best_dict["state_dict"])
    net.to("cpu")
    net.eval()
    dataset_dict = train_val_test.dataset_dict

    for phase in ["train", "test"]:
        dataset = dataset_dict[phase]
        seq = dataset.seq

        pred_list = dataset[0][0].numpy()
        label_list = dataset.get_label()
        with torch.set_grad_enabled(False):
            for i in range(len(dataset)):
                inputs = torch.from_numpy(pred_list[-seq:]).unsqueeze(0)
                out = net(inputs).numpy()
                feature = dataset.get_feature(i)
                out = np.append(out, feature)
                pred_list = np.vstack([pred_list, out])
        pred_list = pred_list[:, 0]
        pred_list = train_val_test.inverse_standard(pred_list)
        label_list = train_val_test.inverse_standard(label_list)
        mae = sum(abs(pred_list[seq:] - label_list[seq:]))/len(pred_list[seq:])

        if plot:
            plt.figure(figsize=(12, 8))
            x=np.arange(len(pred_list))
            plt.plot(seq - 1, pred_list[seq - 1], ".", c="C0", markersize=20)
            sns.lineplot(x=x, y=pred_list, label="predict", linewidth=4)
            sns.lineplot(x=x, y=label_list, label="gt", linewidth=4)
            plt.title(f"pred_{phase} (mae:{mae:.3f})")
            plt.legend(fontsize=16)
            plt.savefig(f"./result_img/{net_name}_{phase}_pred.png")
    return mae  # testのmae

def run_repeatedly(Net, net_name, net_config, train_val_test, epoch=30000, lr=0.001, patience=-1, repeat_num=100):
    mae_list = []
    for _ in tqdm(range(repeat_num), desc=net_name):
        mae_list.append(run(Net, net_name, net_config, train_val_test, epoch, lr=lr,
                            use_best=True, plot=False, log=False,
                            patience=patience))
    fig, ax = plt.subplots()
    sns.boxplot(data=[mae_list], whis=[0, 100])
    sns.stripplot(data=[mae_list], size=4, color="white", edgecolor="black", linewidth=1)
    ax.set_xticklabels([net_name])
    plt.savefig(f"./result_img/boxplot_{net_name}.png")
    return mae_list