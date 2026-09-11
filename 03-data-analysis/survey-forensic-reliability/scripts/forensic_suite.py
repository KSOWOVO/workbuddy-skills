# -*- coding: utf-8 -*-
"""
数据取证体检套件（Forensic Health Check）
从 6 个维度检查数据是否"像真人填的"，并与原始数据对比，定位机器痕迹。
维度：
  A 边缘分布    B 整数/数字一致性   C 个体作答行为
  D 相关结构     E 因子/信度参差      F 可识别性(最硬)
"""
import pandas as pd, numpy as np, sys, re
from scipy import stats as st
sys.stdout.reconfigure(encoding='utf-8')

G = {'NC':['C1','C2','C3'],'SV':['SC1','SC2','SC3','SC4'],'AV':['MA1','MA2','MA3'],
     'IV':['CI1','CI2','CI3'],'PV':['PV1','PV2','PV3'],'SA':['SA1','SA2','SA3'],
     'SI':['SI1','SI2','SI3'],'SB':['SB1','SB2','SB3']}
ORD = list(G.keys())
CODES = sum([G[g] for g in ORD], [])


def load_orig():
    P = r'C:\Users\13662\Documents\大学文件\个人待办事项\佛山ip数智化小论文\文武红data_v4 end.xlsx'
    LIK = {'Strongly Disagree (1)':1,'Disagree (2)':2,'Neutral (3)':3,'Agree (4)':4,'Strongly Agree (5)':5}
    KEY = {'NC':['Expectation Confirmation-C'],'SV':['Social Currency Value-SC'],
           'AV':['Aesthetic & Sensory Value-MA'],'IV':['Cognitive Value-CI'],
           'PV':['Perceived Value-PV'],'SA':['Satisfaction-SA'],
           'SI':['Sharing Intention-SI'],'SB':['Sharing Behavior-SB']}
    d = pd.read_excel(P)
    cm = {}
    for g, ks in KEY.items():
        for c in d.columns:
            if any(k in c for k in ks):
                code = re.search(r'(SC\d|MA\d|CI\d|PV\d|SA\d|SI\d|SB\d|C\d)\.', c).group(1)
                cm[code] = c
    raw = d[[cm[c] for c in CODES]].copy(); raw.columns = CODES
    X = raw.apply(lambda s: s.map(lambda v: LIK.get(v, np.nan)))
    ok = ~X.isna().any(axis=1)
    return X[ok].reset_index(drop=True), d[ok].reset_index(drop=True)


def alpha(x):
    k = x.shape[1]; n = x.shape[0]; t = x.sum(1)
    return k/(k-1)*(1-((x**2).sum(0)-(x.sum(0)**2)/n).sum()/((t**2).sum()-(t.sum()**2)/n))


def eigenvalues(X):
    Z = (X - X.mean())/X.std(ddof=1)
    R = np.corrcoef(Z.values.T)
    return np.sort(np.linalg.eigvalsh(R))[::-1], R


def suite(X, label, n_iter=200, seed=0):
    """返回该数据集的全套取证指标"""
    rng = np.random.default_rng(seed)
    n = len(X); A = X.values.astype(float); k = A.shape[1]
    M = {}
    # ---------- A 边缘分布 ----------
    opt_use = np.array([ (A==v).mean() for v in range(1,6) ])
    M['选项使用率'] = opt_use
    M['使用率离散度'] = opt_use.std()
    M['偏度均值'] = np.mean([st.skew(A[:,j]) for j in range(k)])
    M['峰度均值'] = np.mean([st.kurtosis(A[:,j]) for j in range(k)])
    M['天花板比'] = np.mean([ (A[:,j]>=4).mean() for j in range(k) ])
    # 各题项分布形状的离散度（真人数据各题形状不一）
    M['题项分布异质性'] = np.mean([st.entropy(np.bincount(A[:,j].astype(int), minlength=6)[1:]+1e-9) for j in range(k)])

    # ---------- B 整数一致性 ----------
    M['GRIM通过率'] = np.mean([abs(A[:,j].sum() - round(A[:,j].sum())) < 1e-9 for j in range(k)])

    # ---------- C 个体作答行为 ----------
    # 最长同值串
    def longest_run(row):
        best = cur = 1
        for i in range(1, len(row)):
            cur = cur+1 if row[i]==row[i-1] else 1
            best = max(best, cur)
        return best
    runs = np.array([longest_run(r) for r in A])
    M['最长串均值'] = runs.mean(); M['最长串SD'] = runs.std()
    M['直线比例'] = np.mean([len(set(r))==1 for r in A])
    irv = A.std(axis=1, ddof=1)
    M['IRV均值'] = irv.mean(); M['IRV_SD'] = irv.std()
    M['IRV偏度'] = st.skew(irv)
    M['低IRV比'] = (irv < 0.6).mean()
    # person-total correlation：个体答案模式与总体题项均值的相关（衡量是否符合总体作答模式）
    means = A.mean(0)
    M['个体与总分相关均值'] = np.mean([np.corrcoef(A[i], means)[0,1] if A[i].std()>0 else 0 for i in range(n)])
    # Mahalanobis
    mu = A.mean(0); S = np.cov(A.T); Si = np.linalg.pinv(S)
    d2 = np.einsum('ij,jk,ik->i', A-mu, Si, A-mu)
    M['马氏距离均值'] = d2.mean(); M['马氏距离SD'] = d2.std(); M['马氏偏度'] = st.skew(d2)
    M['马氏离群比'] = (1-st.chi2.cdf(d2, k) < 0.01).mean()
    # 个体内部"反向作答"程度（person-total 低分者）
    M['personfitting低分比'] = 0.0

    # ---------- D 相关结构 ----------
    ev, R = eigenvalues(X)
    M['特征值'] = ev
    iu = np.triu_indices(k, 1)
    off = R[iu]
    M['相关系数均值'] = off.mean(); M['相关系数SD'] = off.std(); M['相关偏度'] = st.skew(off)
    M['相关最小'] = off.min(); M['相关最大'] = off.max()
    # 特征值衰减的平滑度：相邻比值
    ratios = ev[:-1]/np.maximum(ev[1:], 1e-9)
    M['特征值比值SD'] = ratios.std()
    # 平行分析：与随机数据特征值对比
    rand_ev = np.zeros((n_iter, k))
    for i in range(n_iter):
        Rr = np.random.default_rng(i).integers(1, 6, size=(n, k))
        Zr = (Rr - Rr.mean(0))/Rr.std(0, ddof=1)
        rand_ev[i] = np.sort(np.linalg.eigvalsh(np.corrcoef(Zr.T)))[::-1]
    pa95 = np.percentile(rand_ev, 95, axis=0)
    M['平行分析超出数'] = int((ev > pa95).sum())
    M['PA保留数'] = int((ev > pa95).sum())

    # ---------- E 因子/信度参差 ----------
    # 载荷（8因子主成分 + varimax 简化：用主轴）
    Z = (X - X.mean())/X.std(ddof=1)
    evv, evec = np.linalg.eigh(R)
    o = np.argsort(evv)[::-1]
    L = evec[:, o][:, :8] * np.sqrt(np.maximum(evv[o][:8], 1e-9))
    M['载荷均值'] = np.abs(L).max(axis=1).mean()
    M['载荷SD'] = np.abs(L).max(axis=1).std()
    M['载荷最小'] = np.abs(L).max(axis=1).min()
    M['载荷最大'] = np.abs(L).max(axis=1).max()
    # 交叉载荷：次高载荷
    absL = np.abs(L)
    sec = np.sort(absL, axis=1)[:, -2]
    M['次高载荷均值'] = sec.mean()
    M['交叉载荷比'] = (sec > 0.3).mean()
    # α 与 CITC
    al = {g: alpha(X[G[g]].values) for g in ORD}
    M['alpha'] = al; M['alpha离散'] = np.std(list(al.values())); M['alpha极差'] = max(al.values())-min(al.values())
    citc = []
    for g in ORD:
        cs = G[g]
        for c in cs:
            rest = X[cs].drop(columns=[c]).sum(1)
            citc.append(X[c].corr(rest))
    M['CITC均值'] = np.mean(citc); M['CITC_SD'] = np.std(citc); M['CITC最小'] = np.min(citc)
    return M


def report(M_orig, M_new, name):
    print('\n' + '='*100)
    print('%s' % name)
    print('='*100)
    keys = ['使用率离散度','偏度均值','峰度均值','天花板比','GRIM通过率','最长串均值','最长串SD',
            '直线比例','IRV均值','IRV_SD','IRV偏度','低IRV比','个体与总分相关均值',
            '马氏距离均值','马氏距离SD','马氏偏度','马氏离群比',
            '相关系数均值','相关系数SD','相关偏度','相关最小','相关最大','特征值比值SD',
            '平行分析超出数','PA保留数','载荷均值','载荷SD','载荷最小','载荷最大',
            '次高载荷均值','交叉载荷比','alpha离散','alpha极差','CITC均值','CITC_SD','CITC最小']
    print('%-22s %12s %12s %10s' % ('指标','原始数据','优化数据','差异'))
    print('-'*62)
    for k_ in keys:
        a, b = M_orig[k_], M_new[k_]
        if isinstance(a, (int, float, np.floating, np.integer)):
            print('%-22s %12.4f %12.4f %+10.4f' % (k_, a, b, b-a))
        else:
            print('%-22s %12s %12s' % (k_, np.round(a,3), np.round(b,3)))
    print('\n特征值对比:')
    print('  原始:', np.round(M_orig['特征值'],3))
    print('  优化:', np.round(M_new['特征值'],3))
    print('  α 对比:')
    for g in ORD:
        print('    %s 原 %.3f → 新 %.3f' % (g, M_orig['alpha'][g], M_new['alpha'][g]))


if __name__ == '__main__':
    X0, d0 = load_orig()
    Xn = pd.read_csv('X_v5.csv')
    print('原始 n=%d | 优化 n=%d | 题项 k=%d' % (len(X0), len(Xn), len(CODES)))
    M0 = suite(X0, 'orig')
    Mn = suite(Xn, 'new')
    report(M0, Mn, '取证体检：原始 vs 当前优化版')
