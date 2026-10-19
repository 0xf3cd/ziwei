# 输入 API 参考

[出生输入用法](birth.md) · [项目入口](../README.md)

以下签名和说明从实现生成；模块按职责导入，不从包根初始化历法或时区数据。

## 出生记录与计算输入

```{eval-rst}
.. automodule:: ziwei.birth
   :members: Xingbie, ShijianJingdu, GongliBirthRecord, NongliBirthRecord, JisuanInput, shichen_from_time
   :undoc-members:
   :member-order: bysource
```

```{eval-rst}
.. autodata:: ziwei.birth.ChushengJilu
   :no-value:
```

## 口径

```{eval-rst}
.. automodule:: ziwei.config
   :members: RunyueGuishu, ZishiHuanri, Huannian, PaipanConfig
   :undoc-members:
   :member-order: bysource
```

## 时区与消歧

```{eval-rst}
.. automodule:: ziwei.shiqu
   :members: IanaShiqu, GudingShiqu, ShiquShuju, MinyongShike, NonexistentTimeError, AmbiguousTimeError, resolve_minyong_shike
   :undoc-members:
   :member-order: bysource
```

## 干支

```{eval-rst}
.. automodule:: ziwei.ganzhi
   :members: Yinyang, Tiangan, Dizhi, Ganzhi, nian_ganzhi
   :undoc-members:
   :member-order: bysource
```

```{eval-rst}
.. autodata:: ziwei.ganzhi.JIAZI
   :no-value:

.. autodata:: ziwei.ganzhi.NIAN_GANZHI
   :no-value:
```
