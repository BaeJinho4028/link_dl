import torch
from torch import nn, optim
from torch.utils.data import DataLoader, random_split
from datetime import datetime
import os
import wandb
from pathlib import Path

BASE_PATH = str(Path(__file__).resolve().parent.parent.parent) # BASE_PATH: /Users/yhhan/git/link_dl
import sys
sys.path.append(BASE_PATH)

CURRENT_FILE_PATH = os.path.dirname(os.path.abspath(__file__))
CHECKPOINT_FILE_PATH = os.path.join(CURRENT_FILE_PATH, "checkpoints")
if not os.path.isdir(CHECKPOINT_FILE_PATH):
  os.makedirs(os.path.join(CURRENT_FILE_PATH, "checkpoints"))

from _01_code._06_fcn_best_practice.e_arg_parser import get_parser
from _01_code._03_real_world_data_to_tensors.m_time_series_dataset_dataloader import BikesDataset
from _01_code._10_rnn.f_rnn_trainer import CustomRegressionTrainer


def get_bikes_data():
  bikes_dataset = BikesDataset()
  print(bikes_dataset)

  bikes_train, bikes_validation, bikes_test = random_split(bikes_dataset, [0.7, 0.2, 0.1])

  print("Num Train Samples: ", len(bikes_train))
  print("Num Validation Samples: ", len(bikes_validation))
  print("Num Test Samples: ", len(bikes_test))

  train_data_loader = DataLoader(dataset=bikes_train, batch_size=wandb.config.batch_size, shuffle=True)
  validation_data_loader = DataLoader(dataset=bikes_validation, batch_size=wandb.config.batch_size)
  test_data_loader = DataLoader(dataset=bikes_test, batch_size=wandb.config.batch_size)

  return train_data_loader, validation_data_loader, test_data_loader


def get_model():
  class MyModel(nn.Module):
    def __init__(self, n_input, n_output):
      super().__init__()

      self.rnn = nn.RNN(input_size=n_input, hidden_size=128, num_layers=2, batch_first=True)
      self.fcn = nn.Linear(in_features=128, out_features=n_output)

    def forward(self, x):
      x, hidden = self.rnn(x)
      x = self.fcn(x)
      return x

  my_model = MyModel(n_input=19, n_output=1)

  return my_model


def main(args):
  run_time_str = datetime.now().astimezone().strftime('%Y-%m-%d_%H-%M-%S')

  config = {
    'epochs': args.epochs,
    'batch_size': args.batch_size,
    'validation_intervals': args.validation_intervals,
    'learning_rate': args.learning_rate,
    'early_stop_patience': args.early_stop_patience
  }

  project_name = "rnn_bikes"
  wandb.init(
    mode="online" if args.wandb else "disabled",
    project=project_name,
    notes="bikes experiment with rnn",
    tags=["rnn", "bikes"],
    name=run_time_str,
    config=config
  )
  print(args)
  print(wandb.config)

  train_data_loader, validation_data_loader, test_data_loader = get_bikes_data()
  device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
  print(f"Training on device {device}.")

  model = get_model()
  model.to(device)
  wandb.watch(model)

  optimizer = optim.Adam(model.parameters(), lr=wandb.config.learning_rate)

  classification_trainer = CustomRegressionTrainer(
    project_name, model, optimizer, train_data_loader, validation_data_loader, None,
    run_time_str, wandb, device, CHECKPOINT_FILE_PATH
  )
  classification_trainer.train_loop()

  wandb.finish()

  test(project_name, test_data_loader)


def test(project_name, test_data_loader):
  test_model = get_model()

  latest_file_path = os.path.join(
    CHECKPOINT_FILE_PATH, f"{project_name}_checkpoint_latest.pt"
  )
  print("MODEL FILE: {0}".format(latest_file_path))
  test_model.load_state_dict(torch.load(latest_file_path, map_location=torch.device('cpu')))

  test_model.eval()

  with torch.no_grad():
    for test_batch in test_data_loader:
      input_test = test_batch['input']
      target_test = test_batch['target']

      output_test = test_model(input_test)

      for output_daily, target_daily in zip(output_test, target_test):
        for date, (output, target) in enumerate(zip(output_daily, target_daily)):
          print("{0:2}: {1:6.2f} <--> {2:6.2f} (Loss: {3:6.2f})".format(
            date, output.item(), target.item(), (target.item() - output.item())
          ))


if __name__ == "__main__":
  parser = get_parser()
  args = parser.parse_args()
  main(args)
  # python _01_code/_10_rnn/h_bikes_train_and_test_rnn.py -v 100