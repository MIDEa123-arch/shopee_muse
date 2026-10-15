Adapted from Alibaba MUSE, Apache-2.0.
Source: https://github.com/alimama-tech/MUSE
Commit: 85eea1587164cd24eb6223d3d0243aca955af980
Changes: package-relative imports. CPU serving, checkpoint loading and preprocessing live in ../model.py. Original trained forward behavior is retained, including Dice on output and recent-sequence cosine passed to SA-TA.
