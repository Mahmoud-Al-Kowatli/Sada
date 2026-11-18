"""B0 baseline: ResNet-18 over LFCC "images" (1 x 60 x T). Same definition is imported by the
training notebook so service and training never drift apart."""
import torch
import torch.nn as nn
import torch.nn.functional as F


class BasicBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, stride: int = 1):
        super().__init__()
        self.c1 = nn.Conv2d(in_ch, out_ch, 3, stride, 1, bias=False)
        self.b1 = nn.BatchNorm2d(out_ch)
        self.c2 = nn.Conv2d(out_ch, out_ch, 3, 1, 1, bias=False)
        self.b2 = nn.BatchNorm2d(out_ch)
        self.short = nn.Sequential()
        if stride != 1 or in_ch != out_ch:
            self.short = nn.Sequential(nn.Conv2d(in_ch, out_ch, 1, stride, bias=False), nn.BatchNorm2d(out_ch))

    def forward(self, x):
        out = F.relu(self.b1(self.c1(x)))
        out = self.b2(self.c2(out))
        return F.relu(out + self.short(x))


class LfccResNet18(nn.Module):
    def __init__(self, n_classes: int = 2, width: int = 16):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv2d(1, width, 3, 1, 1, bias=False), nn.BatchNorm2d(width), nn.ReLU())
        chans = [width, width * 2, width * 4, width * 8]
        layers = []
        in_ch = width
        for i, ch in enumerate(chans):
            stride = 1 if i == 0 else 2
            layers += [BasicBlock(in_ch, ch, stride), BasicBlock(ch, ch, 1)]
            in_ch = ch
        self.layers = nn.Sequential(*layers)
        self.head = nn.Linear(in_ch, n_classes)

    def forward(self, x):  # x: (N, 1, 60, T)
        h = self.layers(self.stem(x))
        h = F.adaptive_avg_pool2d(h, 1).flatten(1)
        return self.head(h)
