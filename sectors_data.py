"""板块分类配置（与业务逻辑分离）

这份精选关注池仍可通过 sector_analysis.py 使用。
想做全市场扫描请改用 universe.tech_largecap_universe() 等动态股票池。
"""

SECTORS: dict[str, list[str]] = {
    # 大盘指数 ETF
    "指数ETF": ["SPY.US", "QQQ.US", "DIA.US", "IWM.US", "RSP.US"],
    # 消费电子 / 硬件
    "消费电子/硬件": ["AAPL.US", "DELL.US", "HPQ.US", "LOGI.US"],
    # 互联网 / 广告
    "互联网/广告": ["GOOG.US", "META.US", "SNAP.US", "PINS.US", "TTD.US", "RDDT.US"],
    # 流媒体 / 内容
    "流媒体/内容": ["NFLX.US", "DIS.US", "SPOT.US", "ROKU.US", "WBD.US"],
    # 电商 / 云
    "电商/云": ["AMZN.US", "SHOP.US", "MELI.US", "SE.US", "PDD.US"],
    # 企业软件 / 云基础设施
    "企业软件/云": ["MSFT.US", "CRM.US", "ORCL.US", "NOW.US", "WDAY.US", "INTU.US"],
    # AI 基础设施 (GPU/芯片/服务器)
    "AI基础设施": ["NVDA.US", "AMD.US", "AVGO.US", "TSM.US", "ARM.US", "SMCI.US", "MRVL.US"],
    # AI 应用 / 数据
    "AI应用/数据": ["PLTR.US", "SNOW.US", "MDB.US", "DDOG.US", "ELASTIC.US", "AI.US"],
    # 存储 / 内存
    "存储/内存": ["MU.US", "WDC.US", "STX.US", "NTAP.US"],
    # 传统半导体 / 模拟
    "传统半导体": ["QCOM.US", "INTC.US", "TXN.US", "ADI.US", "NXPI.US", "ON.US"],
    # 网络安全
    "网络安全": ["PANW.US", "CRWD.US", "ZS.US", "FTNT.US", "NET.US", "S.US"],
    # 网络 / 通信设备
    "网络/通信": ["CSCO.US", "ANET.US", "JNPR.US", "MSI.US"],
    # 金融
    "金融": ["JPM.US", "GS.US", "MS.US", "BAC.US", "WFC.US", "BRK.B.US", "C.US", "SCHW.US"],
    # 支付/金融科技
    "支付/Fintech": ["V.US", "MA.US", "PYPL.US", "SQ.US", "COIN.US", "FI.US"],
    # 医疗保健
    "医疗保健": ["UNH.US", "JNJ.US", "LLY.US", "ABBV.US", "MRK.US", "PFE.US", "TMO.US", "ISRG.US"],
    # 消费
    "消费": ["TSLA.US", "COST.US", "WMT.US", "HD.US", "MCD.US", "SBUX.US", "NKE.US", "TJX.US"],
    # 能源
    "能源": ["XOM.US", "CVX.US", "COP.US", "SLB.US", "EOG.US", "OXY.US"],
    # 工业
    "工业": ["CAT.US", "DE.US", "GE.US", "HON.US", "UNP.US", "RTX.US", "LMT.US", "BA.US"],
    # 公用事业 / 防御
    "公用/防御": ["NEE.US", "DUK.US", "SO.US", "D.US", "XLU.US"],
    # 地产 REITs
    "地产REITs": ["AMT.US", "PLD.US", "CCI.US", "EQIX.US", "O.US", "SPG.US"],
}
