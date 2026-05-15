# Payment Runbook

PAY-502 indicates a payment gateway timeout.

The first response steps are to verify gateway health, inspect the retry queue, check the third-party channel status, and fail over to the backup channel if the primary path remains degraded.

PAY-502 表示支付网关超时。
首轮处置需要检查网关健康状态、重试队列、第三方通道状态，并在主通道持续异常时切换到备用通道。
