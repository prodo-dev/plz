import random

import torch
from torch import nn as nn, optim as optim


class LeNet(nn.Module):
    # Use Chongelsohn's constant as the seed
    torch.manual_seed(34)
    torch.cuda.manual_seed_all(34)
    random.seed(34)

    def __init__(self, device, learning_rate, momentum):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 15, kernel_size=6)
        self.maxPool2d = nn.MaxPool2d(kernel_size=2)
        self.relu = nn.ReLU()
        self.conv2 = nn.Conv2d(15, 30, kernel_size=6)
        self.conv2_dropout = nn.Dropout2d(0.5)
        self.linear1 = None
        self.dropout = nn.Dropout(0)
        self.linear2 = nn.Linear(50, 10)
        self.log_softmax = nn.LogSoftmax(dim=1)
        self.device = device
        self.learning_rate = learning_rate
        self.momentum = momentum
        self.loss = nn.NLLLoss()
        self.optimizer = None

    def forward(self, x):
        batch_size = x.size(0)
        for l in self.conv1, self.maxPool2d, self.relu, self.conv2, \
                self.conv2_dropout, self.maxPool2d, self.relu:
            x = l(x)

        # Create the first linear layer now that we know the dimension
        if self.linear1 is None:
            self.linear1 = nn.Linear(x.view(-1).size(0)//batch_size, 50)
            self.linear1 = self.linear1.to(self.device)
            self.optimizer = optim.SGD(
                self.parameters(),
                lr=self.learning_rate,
                momentum=self.momentum)

        x = x.view(batch_size, self.linear1.in_features)
        for l in self.linear1, self.relu, self.dropout, self.linear2, \
                self.log_softmax:
            x = l(x)

        return x

    def epoch(self, data_loader) -> float:
        self.train()
        loss = None
        for batch_number, (predictors, target) in enumerate(data_loader):
            predictors, target = \
                predictors.to(self.device), target.to(self.device)
            output = self.forward(predictors)
            self.optimizer.zero_grad()
            loss = self.loss(output, target)
            loss.backward()
            self.optimizer.step()
        return loss.item()

    def evaluation(self, test_loader) -> float:
        self.eval()
        correct = 0
        for data, target in test_loader:
            data, target = data.to(self.device), target.to(self.device)
            output = self.forward(data)
            predicted = output.max(1, keepdim=True)[1]
            correct += predicted.eq(target.view_as(predicted)).sum().item()

        accuracy = 100. * correct / len(test_loader.dataset)
        return accuracy
