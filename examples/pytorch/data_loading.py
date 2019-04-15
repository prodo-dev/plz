from torchvision import datasets, transforms
from torch.utils.data import DataLoader


def create_loader(
        input_directory: str,
        batch_size: int,
        pin_memory: bool,
        is_training: bool):
    return DataLoader(
        datasets.MNIST(
            input_directory,
            train=is_training,
            transform=transforms.ToTensor()),
        batch_size=batch_size,
        shuffle=True,
        num_workers=1,
        pin_memory=pin_memory)
