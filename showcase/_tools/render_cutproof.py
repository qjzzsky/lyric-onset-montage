# -*- coding: utf-8 -*-
"""统一双轨刀口图：与《骄傲的少年》《意外》同版式（1600x900 深色）"""
import numpy as np, json, os, subprocess, wave, tempfile, importlib.util
from PIL import Image, ImageDraw, ImageFont

# check_cut.py 与图同源：从仓库里加载，保证波形/网格口径一致
import pathlib
_p = pathlib.Path(__file__).resolve().parents[2] / "skills" / "lyric-onset-montage" / "scripts" / "check_cut.py"
spec = importlib.util.spec_from_file_location("cc", str(_p)); cc = importlib.util.module_from_spec(spec); spec.loader.exec_module(cc)

BG="#0f1115"; FG="#e8edf2"; DIM="#8b939c"; SUB="#cdd4dc"
WAVE="#8fc3e8"; GRIDC="#4e5763"; RED="#f2403a"; FOOT="#5f6873"
X0,X1 = 48,1552

def F(sz,bold=False):
    cands = [os.path.join(os.environ.get("WINDIR", ""), "Fonts", "msyhbd.ttc" if bold else "msyh.ttc"),
             "/System/Library/Fonts/PingFang.ttc",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for f in cands:
        try: return ImageFont.truetype(f,sz)
        except Exception: pass
    return ImageFont.load_default()

def env_of(sig):
    band = cc.bandpass(sig,300,3000)
    e,t = cc.rms_env(band)
    return e/max(e.max(),1e-9), t

def wave_panel(d,y0,y1,e,tt,T0,T1):
    mid=(y0+y1)//2; hh=(y1-y0)/2*0.92
    d.line([(X0,mid),(X1,mid)],fill="#1d232b")
    for x in range(X0,X1+1):
        t=T0+(x-X0)/(X1-X0)*(T1-T0)
        i=int(np.searchsorted(tt,t)); j=min(len(e)-1,i+2)
        a=float(e[i:j+1].max()) if j>i else float(e[min(i,len(e)-1)])
        yy=mid-a*hh
        d.line([(x,yy),(x,mid)],fill=WAVE)
        d.line([(x,mid),(x,2*mid-yy)],fill=WAVE)

def grid_lines(d,phase,P,T0,T1,y0,y1):
    k0=int(np.ceil((T0-phase)/P)); k1=int(np.floor((T1-phase)/P))
    for k in range(k0,k1+1):
        t=phase+k*P
        x=X0+(t-T0)/(T1-T0)*(X1-X0)
        d.line([(x,y0),(x,y1)],fill=GRIDC)

def vx(t,T0,T1): return X0+(t-T0)/(T1-T0)*(X1-X0)

def rot_text(txt,font,color):
    tmp=ImageDraw.Draw(Image.new("RGB",(1,1)))
    bb=tmp.textbbox((0,0),txt,font=font); w=bb[2]-bb[0]+8; h=bb[3]-bb[1]+10
    im=Image.new("RGBA",(w,h),(0,0,0,0)); dd=ImageDraw.Draw(im)
    dd.text((4,-bb[1]+5),txt,font=font,fill=color)
    return im.rotate(90,expand=True)

def badge(d,x,y,txt,font):
    bb=d.textbbox((0,0),txt,font=font); w=bb[2]-bb[0]+16; h=bb[3]-bb[1]+12
    d.rectangle([x-w/2,y-h/2,x+w/2,y+h/2],fill="#1b1f26",outline="#ffffff",width=1)
    d.text((x-w/2+8,y-h/2+5),txt,font=font,fill="#ffffff")

def arrow(d,x1,x2,y):
    d.line([(x1,y),(x2,y)],fill="#ffffff",width=2)
    for xx,dirn in ((x1,1),(x2,-1)):
        d.polygon([(xx,y),(xx+7*dirn,y-4),(xx+7*dirn,y+4)],fill="#ffffff")

def frame(title,sub,data):
    img=Image.new("RGB",(1600,900),BG); d=ImageDraw.Draw(img)
    d.text((X0,34),title,font=F(40,True),fill=FG)
    d.text((X0,94),sub,font=F(21),fill=SUB)
    d.text((X0,126),data,font=F(16),fill=DIM)
    return img,d

def finish(img,d,concl,leg1,leg2,foot1,foot2):
    d.text((X0,752),concl,font=F(21),fill=FG)
    y=792
    d.line([(X0,y+8),(X0+34,y+8)],fill=GRIDC,width=2); d.text((X0+44,y),leg1,font=F(16),fill=SUB)
    d.line([(X0+300,y+8),(X0+334,y+8)],fill=RED,width=3);   d.text((X0+344,y),leg2,font=F(16),fill=SUB)
    d.text((X0,830),foot1,font=F(14),fill=DIM)
    d.text((X0,856),foot2,font=F(12),fill=FOOT)

def two_tracks(onsets_text, cuts, T0, T1, phase, P, e, tt, tag1, tag2, label_pos="bottom"):
    img,d=frame(*(
        # 由调用方覆盖
        ("","","")
    ))
    return img,d

# ══════════ 1. 推开世界的门 ══════════
def render_tuimen():
    tmp=tempfile.mkdtemp()
    sig=cc.load_audio(os.environ.get("TUIMEN_MP4", "<推开门成片.mp4>"),tmp)
    e,tt=env_of(sig)
    P=0.8570846777887933; PH=0.275
    T0,T1=12.6,31.9
    cuts=[13.30,16.60,20.15,23.35,27.15,30.70]
    img,d=frame("字头对齐 vs 鼓点对齐",
      "《推开世界的门》55s 版（全片 16 刀／本窗口 6 刀）：切点贴人耳落点，比检测器报的持续段上升沿晚中位 245ms ｜ 改贴最近网格线则中位差 214ms",
      "音源 成片音轨 55.00s（演唱 杨乃文｜词曲 火星电台 / 黄少峰） ｜ 窗口 12.6–31.9s ｜ 曲速 70.0 BPM（格距 0.857s，相位集中度 0.60）｜ 网格＝低频拟合，非人工标拍")
    AU,AD=178,438; BU,BD=462,722
    wave_panel(d,AU,AD,e,tt,T0,T1); grid_lines(d,PH,P,T0,T1,AU,AD)
    d.text((X1,AU-24),"① 节拍网格（70.0 BPM，等间隔）",font=F(16),fill=SUB,anchor="ra")
    wave_panel(d,BU,BD,e,tt,T0,T1)
    for c in cuts:
        x=vx(c,T0,T1); d.line([(x,BU),(x,BD)],fill=RED,width=3)
    d.text((X1,BU-24),"② 歌词切点（人耳验收的落点）",font=F(16),fill=SUB,anchor="ra")
    for c,txt in [(13.30,"捧着一颗不懂计较的认真"),(20.15,"吻过你的眼睛 就无畏的青春"),(27.15,"左手的泥呀"),(30.70,"知己的花衣裳")]:
        lab=rot_text(txt,F(15),"#ff7b72")
        img.paste(lab,(int(vx(c,T0,T1))+4,int(BD-6-lab.height)),lab)
    xa,xb=vx(13.05,T0,T1),vx(13.30,T0,T1)
    d.line([(xa,BU),(xa,BD)],fill="#ffffff",width=1)
    arrow(d,xa,xb,BD-52); badge(d,xb+64,BD-96,"+250ms",F(20,True))
    finish(img,d,
      "典型一处：「捧着一颗」旧切点 13.05s、检测器报的持续段上升沿 13.05s —— 包络说「刚好」，耳朵说「早了」，后移 250ms 到 13.30s",
      "鼓点网格","人耳切点",
      "为什么 beat 检测测不到：它只给等间隔网格，不知道哪一下开始一句；人耳听的是元音唱出来的落点，比能量抬头晚 0.15–0.25s。",
      "数据：《推开世界的门》镜头表 + 逐刀字头表（10 刀实测）｜ 网格 check_cut.py fit_grid")
    out=str(pathlib.Path(__file__).resolve().parents[1]/"推开世界的门-55s"/"cut-proof.png")
    img.save(out,quality=95); print("saved",out,os.path.getsize(out)//1024,"KB")

# ══════════ 2. 快乐小神仙 ══════════
def render_kuaile():
    # 素材路径用环境变量给，仓库里不写本机路径
    wav=os.environ.get("SONG", "kuaile.wav")
    with wave.open(wav) as w:
        sig=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768.0
    e,tt=env_of(sig)
    P=0.5409; PH=0.03
    T0,T1=48.8,65.4
    rows=json.load(open(os.environ.get("ONSETS", "kuaile-onsets.json"),encoding="utf-8"))
    pick=[r for r in rows if T0<=r["onset"]<=T1]
    img,d=frame("字头对齐 vs 鼓点对齐",
      "《快乐小神仙》176s 整首 47 刀：歌词烧在画面里，句界靠像素检测；字幕比唱早中位 240ms 只用来缩窗，刀口仍按音轨定 ｜ 按鼓点切中位差 169ms",
      "音源 原曲 176.17s（演唱 天唱组合｜词 张藜｜曲 肖白） ｜ 窗口 48.8–65.4s ｜ 曲速 110.9 BPM（格距 0.541s，相位集中度 0.59）｜ 字幕轨不存在，AI 字幕也失败")
    AU,AD=178,438; BU,BD=462,722
    wave_panel(d,AU,AD,e,tt,T0,T1); grid_lines(d,PH,P,T0,T1,AU,AD)
    d.text((X1,AU-24),"① 节拍网格（110.9 BPM，等间隔）",font=F(16),fill=SUB,anchor="ra")
    wave_panel(d,BU,BD,e,tt,T0,T1)
    # 字幕起点（橙虚线）
    for r in pick:
        x=vx(r["cand"],T0,T1)
        for yy in range(BU,BD,14): d.line([(x,yy),(x,min(yy+7,BD))],fill="#ffb454",width=2)
    # 字头红线
    for r in pick:
        x=vx(r["onset"],T0,T1); d.line([(x,BU),(x,BD)],fill=RED,width=3)
    d.text((X1,BU-24),"② 字幕起点（橙色虚线，只用于缩窗）／ 实测字头（红线）",font=F(16),fill=SUB,anchor="ra")
    # 选一条存疑刀做标注：53.707 字头，字幕 53.467
    r=[x for x in pick if abs(x["onset"]-53.707)<0.05][0]
    xa,xb=vx(r["cand"],T0,T1),vx(r["onset"],T0,T1)
    arrow(d,xa,xb,BD-52); badge(d,xb+62,BD-96,"+240ms",F(19,True))
    lab=rot_text("到宇宙里游一游",F(15),"#ff7b72")
    img.paste(lab,(int(vx(r["onset"],T0,T1))+3,int(BD-6-lab.height)),lab)
    finish(img,d,
      "同一个道理：字幕定「这句大概在哪」，字头靠音轨自己量 —— 字幕的 240ms 偏移没被带进成片；47 刀交付后没有要求挪动任何一刀",
      "鼓点网格","实测字头",
      "为什么不能拿字幕当切点：烧录字幕普遍比唱早 0.17–0.27s，照抄就是整片系统性提前；字幕的价值是「句界」，不是「时刻」。",
      "数据：《快乐小神仙》自检报告 + onsets.json（37 段字幕并成 36 句）｜ 网格 check_cut.py fit_grid（110.9 BPM）")
    out=str(pathlib.Path(__file__).resolve().parents[1]/"快乐小神仙-176s"/"cut-proof.png")
    img.save(out,quality=95); print("saved",out,os.path.getsize(out)//1024,"KB")

if __name__=="__main__":
    render_tuimen()
    render_kuaile()
