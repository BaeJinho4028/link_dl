import torch
from torch import optim, nn
from datetime import datetime
import os
import wandb
from pathlib import Path

from torch.utils.data import random_split, DataLoader
from torchvision import datasets, transforms

BASE_PATH = str(Path(__file__).resolve().parent.parent.parent) # BASE_PATH: /Users/yhhan/git/link_dl
import sys
sys.path.append(BASE_PATH)

CURRENT_FILE_PATH = os.path.dirname(os.path.abspath(__file__))
CHECKPOINT_FILE_PATH = os.path.join(CURRENT_FILE_PATH, "checkpoints")
if not os.path.isdir(CHECKPOINT_FILE_PATH):
  os.makedirs(os.path.join(CURRENT_FILE_PATH, "checkpoints"))

import sys
sys.path.append(BASE_PATH)

from _01_code._06_fcn_best_practice.c_trainer import ClassificationTrainer
from _01_code._08_diverse_techniques.a_arg_parser import get_parser
from _01_code._08_diverse_techniques.f_cifar10_train_cnn_with_normalization import \
  get_cnn_model_with_dropout_and_batch_normalization
from _01_code._99_common_utils.utils import get_num_cpu_cores, is_linux, is_windows


def get_augmented_cifar10_data():
  data_path = os.path.join(BASE_PATH, "_00_data", "i_cifar10")

  print("DATA PATH: {0}".format(data_path))

  cifar10_train = datasets.CIFAR10(data_path, train=True, download=True, transform=transforms.ToTensor())

  cifar10_train, cifar10_validation = random_split(cifar10_train, [45_000, 5_000])

  print("Num Train Samples: ", len(cifar10_train))
  print("Num Validation Samples: ", len(cifar10_validation))

  num_data_loading_workers = get_num_cpu_cores() if is_linux() or is_windows() else 0
  print("Number of Data Loading Workers:", num_data_loading_workers)

  train_data_loader = DataLoader(
    dataset=cifar10_train, batch_size=wandb.config.batch_size, shuffle=True,
    pin_memory=True, num_workers=num_data_loading_workers
  )

  validation_data_loader = DataLoader(
    dataset=cifar10_validation, batch_size=wandb.config.batch_size,
    pin_memory=True, num_workers=num_data_loading_workers
  )

  cifar10_transforms = nn.Sequential(
    transforms.ConvertImageDtype(torch.float),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.RandomCrop(32, padding=[0, 2, 3, 4]),
    transforms.RandomAffine(0, shear=10, scale=(0.8, 1.2)),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
    transforms.Normalize(mean=(0.4915, 0.4823, 0.4468), std=(0.2470, 0.2435, 0.2616)),
  )

  return train_data_loader, validation_data_loader, cifar10_transforms


def main(args):
  config = {
    'epochs': args.epochs,
    'batch_size': args.batch_size,
    'validation_intervals': args.validation_intervals,
    'learning_rate': args.learning_rate,
    'early_stop_patience': args.early_stop_patience,
    'weight_decay': args.weight_decay,
    'dropout': args.dropout
  }

  run_time_str = datetime.now().astimezone().strftime('%Y-%m-%d_%H-%M-%S')
  name = "image_augment_and_batch_norm_{0}".format(run_time_str)

  project_name = "cnn_cifar10_with_image_augment_and_batch_norm"
  wandb.init(
    mode="online" if args.wandb else "disabled",
    project=project_name,
    notes="cifar10 experiment with cnn, image_augment, and batch_norm",
    tags=["cnn", "cifar10", "image_augment", "batch_norm"],
    name=name,
    config=config
  )
  print(args)
  print(wandb.config)

  device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
  print(f"Training on device {device}.")

  train_data_loader, validation_data_loader, cifar10_transforms = get_augmented_cifar10_data()

  model = get_cnn_model_with_dropout_and_batch_normalization()

  model.to(device)
  wandb.watch(model)

  optimizer = optim.Adam(model.parameters(), lr=wandb.config.learning_rate, weight_decay=args.weight_decay)

  classification_trainer = ClassificationTrainer(
    project_name, model, optimizer,
    train_data_loader, validation_data_loader, cifar10_transforms,
    run_time_str, wandb, device, CHECKPOINT_FILE_PATH
  )
  classification_trainer.train_loop()

  wandb.finish()


if __name__ == "__main__":
  parser = get_parser()
  args = parser.parse_args()
  main(args)
  # python _01_code/_08_diverse_techniques/g_cifar10_train_cnn_with_image_augmentation_and_batch_normalization.py --wandb --dropout -w 0.002 -v 1
  # python _01_code/_08_diverse_techniques/g_cifar10_train_cnn_with_image_augmentation_and_batch_normalization.py --no-wandb --dropout -w 0.002 -v 1
