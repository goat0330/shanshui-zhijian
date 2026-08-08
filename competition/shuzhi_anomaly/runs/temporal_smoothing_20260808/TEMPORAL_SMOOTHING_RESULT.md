# Temporal probability smoothing result

训练侧：每个摄像头组前60%作support、后40%作query，support只使用模型概率的组内中位数，不使用query标签。
测试侧：只报告无标签概率会怎样变化，不把测试结果当作提升证据。

- train pseudo-query: 333
- train groups: 316
- test images with a context group: 528
- baseline pseudo-query Weighted F1: 0.983557
- best beta: 0.0
- best pseudo-query Weighted F1: 0.983557

| beta | query n | accuracy | weighted F1 | mIoU | changed |
|---:|---:|---:|---:|---:|---:|
| 0.0 | 333 | 0.987988 | 0.983557 | 0.760539 | 0 |
| 0.1 | 333 | 0.987988 | 0.983557 | 0.760539 | 0 |
| 0.2 | 333 | 0.987988 | 0.983557 | 0.760539 | 0 |
| 0.3 | 333 | 0.987988 | 0.983557 | 0.760539 | 0 |
| 0.5 | 333 | 0.981982 | 0.978350 | 0.650474 | 3 |

## Test-side changes

{"0.0": 0, "0.1": 0, "0.2": 0, "0.3": 0, "0.5": 3}

若训练伪query无稳定收益，或测试侧只改变少量且没有标签证据，本路线不进入提交。
