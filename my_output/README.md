## Files and Corresponding Commands

### Parallel Translation: JP + CN + EN

`_三木真一郎_事务所语音样本试听.txt`
```bash
python3 pipeline.py "https://www.bilibili.com/video/BV1Ct411f7nC/?spm_id_from=333.337.search-card.all.click&vd_source=93675b9f5fc7be8a722f7ff16cd66808" --mode both --out ./my_output
```


`なかのひとのなか_三木真一郎_.txt`
```bash
python3 pipeline.py "https://www.bilibili.com/video/BV19tZPYpEzf/?spm_id_from=333.337.search-card.all.click&vd_source=93675b9f5fc7be8a722f7ff16cd66808" --mode both --out ./my_output
```

### Bilingual Translation: JP + CN
`BLCDコレクション_業火顕乱 二重螺旋6_音声CM.txt`
```bash
python3 pipeline.py "https://www.youtube.com/watch?v=hUJzntL4jao" --mode zh --out ./my_output
```

### Transcription Only: JP Raw
`ドラマCD_新宿ラッキーホール_メッセージボイス２_三木眞一郎_.txt`
```bash
python3 pipeline.py "https://www.youtube.com/watch?v=qQ9w7Gw9bOk" --mode none --out ./my_output
```


`ドラマCD_新宿ラッキーホール_試聴１_CV_三木眞一郎_羽多野渉_.txt`
```bash
python3 pipeline.py "https://www.youtube.com/watch?v=9UEzsCNMLjE" --mode none --out ./my_output
```


`安達盛長_CV_三木眞一郎__本編PV_ イケメン源氏伝 あやかし恋えにし.txt`
```bash
python3 pipeline.py "https://www.youtube.com/watch?v=8jXNKyTGjD4" --mode none --out ./my_output
```
