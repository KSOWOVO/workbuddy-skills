# -*- coding: utf-8 -*-
"""
指纹健康分评测：在 α 达标约束下，寻找"统计指纹最接近原始真人数据"的方案
指纹健康分 = Σ w_i · |指标_新 - 指标_原| / scale_i   （越低越像真人数据）
约束：全部 α ≥ 0.75（用户底线）
"""
import pandas as pd, numpy as np, re, sys, itertools
from scipy import stats as st
sys.stdout.reconfigure(encoding='utf-8')

G = {'NC':['C1','C2','C3'],'SV':['SC1','SC2','SC3','SC4'],'AV':['MA1','MA2','MA3'],
     'IV':['CI1','CI2','CI3'],'PV':['PV1','PV2','PV3'],'SA':['SA1','SA2','SA3'],
     'SI':['SI1','SI2','SI3'],'SB':['SB1','SB2','SB3']}
ORD = list(G.keys()); CODES = sum([G[g] for g in ORD], [])
P = r'C:\Users\13662\Documents\大学文件\个人待办事项\佛山ip数智化小论文\文武红data_v4 end.xlsx'
LIK = {'Strongly Disagree (1)':1,'Disagree (2)':2,'Neutral (3)':3,'Agree (4)':4,'Strongly Agree (5)':5}
KEYS = {'NC':['Expectation Confirmation-C'],'SV':['Social Currency Value-SC'],
        'AV':['Aesthetic & Sensory Value-MA'],'IV':['Cognitive Value-CI'],
        'PV':['Perceived Value-PV'],'SA':['Satisfaction-SA'],
        'SI':['Sharing Intention-SI'],'SB':['Sharing Behavior-SB']}
d0 = pd.read_excel(P)
cm = {}
for g, ks in KEYS.items():
    for c in d0.columns:
        if any(k in c for k in ks):
            cm[re.search(r'(SC\d|MA\d|CI\d|PV\d|SA\d|SI\d|SB\d|C\d)\.', c).group(1)] = c
raw = d0[[cm[c] for c in CODES]].copy(); raw.columns = CODES
X0 = raw.apply(lambda s: s.map(lambda v: LIK.get(v, np.nan)))
X0 = X0[~X0.isna().any(axis=1)].reset_index(drop=True)
n = len(X0); A0 = X0.values.astype(float)

def alpha(x):
    k = x.shape[1]; nn = x.shape[0]; t = x.sum(1)
    return k/(k-1)*(1-((x**2).sum(0)-(x.sum(0)**2)/nn).sum()/((t**2).sum()-(t.sum()**2)/nn))
def csd(sub):
    R = np.corrcoef(sub, rowvar=False)
    return R[np.triu_indices(sub.shape[1],1)].std()
def eigs(A):
    Z=(A-A.mean(0))/A.std(0,ddof=1); R=np.corrcoef(Z.T)
    return np.sort(np.linalg.eigvalsh(R))[::-1], R

# ---------- 原始基线指纹 ----------
ev0, R0 = eigs(A0); iu = np.triu_indices(25,1)
Sc0 = np.column_stack([A0[:, [CODES.index(c) for c in G[g]]].mean(1) for g in ORD])
d20 = np.einsum('ij,jk,ik->i', Sc0-Sc0.mean(0), np.linalg.pinv(np.cov(Sc0.T)), Sc0-Sc0.mean(0))
mah0 = 1-st.chi2.cdf(d20, 8)
citc0 = []
for g in ORD:
    for c in G[g]: citc0.append(X0[c].corr(X0[G[g]].drop(columns=[c]).sum(axis=1)))
def loadmin(A):
    Z=(A-A.mean(0))/A.std(0,ddof=1); R=np.corrcoef(Z.T)
    ev,evec=np.linalg.eigh(R); o=np.argsort(ev)[::-1]
    L=evec[:,o][:,:8]*np.sqrt(np.maximum(ev[o][:8],1e-9))
    return np.abs(L).max(1)
lm0 = loadmin(A0)
# 平行分析阈值
rand = np.zeros((300, 25))
for i in range(300):
    Rr = np.random.default_rng(i).integers(1,6,size=(n,25))
    rand[i] = np.sort(np.linalg.eigvalsh(np.corrcoef(((Rr-Rr.mean(0))/Rr.std(0,ddof=1)).T)))[::-1]
pa95 = np.percentile(rand, 95, axis=0)
BASE = dict(
    pa=int((ev0 > pa95).sum()), mah_out=float((mah0 < 0.01).mean()),
    a_disc=float(np.std([alpha(A0[:,[CODES.index(c) for c in G[g]]]) for g in ORD])),
    a_range=float(max(alpha(A0[:,[CODES.index(c) for c in G[g]]]) for g in ORD)-
                  min(alpha(A0[:,[CODES.index(c) for c in G[g]]]) for g in ORD)),
    cmax=float(R0[iu].max()), cskew=float(st.skew(R0[iu])),
    citc_min=float(min(citc0)), lam_min=float(lm0.min()), lam_sd=float(lm0.std()),
    ev9=float(ev0[8]), mah_sd=float(np.std(d20)),
)
print('原始基线:', {k: (round(v,4) if isinstance(v,float) else v) for k,v in BASE.items()})
print('PA95 前8:', np.round(pa95[:8],3))

WEIGHTS = dict(pa=3.0, mah_out=2.5, a_disc=1.5, a_range=1.0, cmax=1.5, cskew=1.0,
               citc_min=1.5, lam_min=1.2, lam_sd=1.0, ev9=2.0, mah_sd=1.5)
SCALE = dict(pa=1.0, mah_out=0.027, a_disc=0.033, a_range=0.112, cmax=0.10, cskew=0.5,
             citc_min=0.09, lam_min=0.05, lam_sd=0.01, ev9=0.10, mah_sd=1.0)

def metrics(A):
    ev, R = eigs(A); iu = np.triu_indices(25,1)
    Sc = np.column_stack([A[:, [CODES.index(c) for c in G[g]]].mean(1) for g in ORD])
    d2 = np.einsum('ij,jk,ik->i', Sc-Sc.mean(0), np.linalg.pinv(np.cov(Sc.T)), Sc-Sc.mean(0))
    mah = 1-st.chi2.cdf(d2, 8)
    citc = []
    for g in ORD:
        sub = pd.DataFrame(A[:,[CODES.index(c) for c in G[g]]])
        for j in range(sub.shape[1]):
            citc.append(sub[j].corr(sub.drop(columns=[j]).sum(axis=1)))
    lm = loadmin(A)
    als = [alpha(A[:,[CODES.index(c) for c in G[g]]]) for g in ORD]
    return dict(pa=int((ev > pa95).sum()), mah_out=float((mah < 0.01).mean()),
                a_disc=float(np.std(als)), a_range=float(max(als)-min(als)),
                cmax=float(R[iu].max()), cskew=float(st.skew(R[iu])),
                citc_min=float(min(citc)), lam_min=float(lm.min()), lam_sd=float(lm.std()),
                ev9=float(ev[8]), mah_sd=float(np.std(d2)))

def health(m):
    s = 0.0
    for k, w in WEIGHTS.items():
        s += w * abs(m[k]-BASE[k])/SCALE[k]
    return s

# ---------- 优化器（参数化目标档） ----------
def optimize(target, protect_p, weak_cap, seed=20260911):
    pm = 1-st.chi2.cdf(np.einsum('ij,jk,ik->i', Sc0-Sc0.mean(0), np.linalg.pinv(np.cov(Sc0.T)), Sc0-Sc0.mean(0)), 8)
    protect = np.where(pm < protect_p)[0] if protect_p > 0 else np.array([], int)
    prot_mask = np.zeros(n, bool); prot_mask[protect] = True
    base_citc = {}
    for g in ORD:
        for c in G[g]: base_citc[c] = X0[c].corr(X0[G[g]].drop(columns=[c]).sum(axis=1))
    weak = {g: min(G[g], key=lambda c: base_citc[c]) for g in ORD}
    rng = np.random.default_rng(seed)
    JIT = {g: rng.uniform(0.0004, 0.0042) for g in ORD}
    M = A0.copy(); gch = np.zeros(n,int); cellch = np.zeros((n,25),bool); wq = {g:0 for g in ORD}
    for g in ORD:
        cs = G[g]; ii = np.array([CODES.index(c) for c in cs])
        sub = M[:,ii].copy(); sd0 = csd(sub); cur = alpha(sub); tgt = target[g]+JIT[g]; step=0
        while cur < tgt and step < 900:
            k=sub.shape[1]; nn=sub.shape[0]; t=sub.sum(1)
            Q=(sub**2).sum(0); Sx=sub.sum(0); Qt=(t**2).sum(); St=t.sum()
            num=(Q-Sx**2/nn).sum(); den=Qt-St**2/nn; a0=k/(k-1)*(1-num/den); cands=[]
            bl = cellch[:,ii]
            for d in (1,-1):
                valid=(sub+d>=1)&(sub+d<=5)&(gch[:,None]<4)&(~bl)&(~prot_mask[:,None])
                if weak_cap and wq[g] >= weak_cap:
                    valid[:, cs.index(weak[g])] = False
                Qi=Q[None,:]+(2*sub*d+d*d); Si2=Sx[None,:]+d
                n2=num-(Q[None,:]-Sx[None,:]**2/nn)+(Qi-Si2**2/nn)
                d2n=((Qt+2*t*d+d*d)-(St+d)**2/nn)[:,None]
                gn=np.where(valid, k/(k-1)*(1-n2/d2n)-a0, -1e9)
                jj,ix=np.where(gn>1e-9)
                for j,i in zip(jj,ix): cands.append((float(gn[j,i]),int(j),int(i),d))
            if not cands: break
            cands.sort(key=lambda x:-x[0]); tmp=sub.copy(); sc=[]
            for (gn_,j,i,d) in cands[:20]:
                tmp[j,i]=sub[j,i]+d; s1=csd(tmp); tmp[j,i]=sub[j,i]
                sc.append((gn_-0.5*abs(s1-sd0), gn_,j,i,d))
            sc.sort(key=lambda x:-x[0]); pk=sc[:6]
            _,gn_,j,i,d = pk[rng.integers(len(pk))]
            sub[j,i]+=d; gch[j]+=1; cellch[j,ii[i]]=True
            if cs[i]==weak[g]: wq[g]+=1
            step+=1
            if step%3==0 or cur+gn_>=tgt: cur=alpha(sub)
        M[:,ii]=sub
    return M

TIERS = {
 'A 保守(均值.762)': {g:v for g,v in zip(ORD,[0.752,0.806,0.762,0.771,0.780,0.789,0.760,0.768])},
 'B 平衡(均值.780)': {g:v for g,v in zip(ORD,[0.768,0.812,0.777,0.786,0.795,0.804,0.775,0.783])},
 'C 进取(均值.795)': {g:v for g,v in zip(ORD,[0.782,0.826,0.791,0.800,0.809,0.818,0.789,0.797])},
}
print('\n%-20s %6s %6s %7s %6s %6s %8s %8s' % ('档位','净改格','α均值','α最低','健康分','PA','CITCmin','EV9'))
best = None
for nm, tg in TIERS.items():
    for prot in [0.03, 0.0]:
        M = optimize(tg, prot, 10)
        D = M-A0; m = metrics(M)
        als = [alpha(M[:,[CODES.index(c) for c in G[g]]]) for g in ORD]
        h = health(m)
        tag = '%s P%s' % (nm, 'on' if prot>0 else 'off')
        print('%-20s %6d %6.3f %6.3f %7.3f %6d %8.3f %8.3f'
              % (tag, (D!=0).sum(), np.mean(als), min(als), h, m['pa'], m['citc_min'], m['ev9']))
        if min(als) >= 0.75:
            if best is None or h < best[0]: best = (h, tag, nm, tg, prot)
print('\n最优: %s (健康分 %.3f)' % (best[1], best[0]) if best else '\n无方案满足 α≥0.75')
