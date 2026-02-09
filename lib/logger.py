import os
import logging
import datetime
import sys

def logConfig():
    logger = logging.getLogger('main')
    
    # 避免重複添加 handler
    if logger.handlers:
        return
    
    if( not os.path.exists('./log')):
        os.mkdir('./log')

    #Normal Logger
    formatter = logging.Formatter('[%(levelname)s %(asctime)s] %(message)s')

    log_filename = datetime.datetime.now().strftime("./log/log.txt")
    filelogHandler = logging.FileHandler(log_filename,mode='w', encoding='utf-8')  # 'w' = 覆寫模式
    filelogHandler.setLevel(logging.INFO)
    filelogHandler.setFormatter(formatter)

    #Error Logger
    log_filename = datetime.datetime.now().strftime("./log/log.err")
    errlogHandler = logging.FileHandler(log_filename,mode='w', encoding='utf-8')  # 'w' = 覆寫模式
    errlogHandler.setLevel(logging.ERROR)
    errlogHandler.setFormatter(formatter)   

    #Console
    consoleHandler = logging.StreamHandler(sys.stdout)
    consoleHandler.setLevel(logging.INFO)
    consoleHandler.setFormatter(formatter)

    logger.addHandler(filelogHandler)
    logger.addHandler(errlogHandler)
    logger.addHandler(consoleHandler)
    logger.setLevel(logging.DEBUG)
    

    return

def LogEvt(msg):
    """記錄一般事件訊息"""
    logging.getLogger('main').info(msg)


def LogErr(msg):
    """記錄錯誤訊息"""
    logging.getLogger('main').error(msg)


def LogWarn(msg):
    """記錄警告訊息"""
    logging.getLogger('main').warning(msg)


def LogDebug(msg):
    """記錄除錯訊息"""
    logging.getLogger('main').debug(msg)


def LogSection(title):
    """記錄區段標題（帶分隔線）"""
    logging.getLogger('main').info("")
    logging.getLogger('main').info("=" * 60)
    logging.getLogger('main').info(f"  {title}")
    logging.getLogger('main').info("=" * 60)
    logging.getLogger('main').info("")


def LogStep(step_number, description):
    """記錄測試步驟"""
    logging.getLogger('main').info("=" * 60)
    logging.getLogger('main').info(f"[STEP {step_number}] {description}")
    logging.getLogger('main').info("=" * 60)


def LogResult(passed, message):
    """記錄測試結果"""
    logger = logging.getLogger('main')
    if passed:
        logger.info(f"✓ [PASS] {message}")
    else:
        logger.error(f"✗ [FAIL] {message}")

logConfig()