# T-ALNS-RRD 论文公式递进说明文档

> 论文：**Optimizing urban last mile delivery efficiency through dynamic vehicle routing heuristics and traffic flow analysis**  
> 说明：本文档将论文中的编号公式按逻辑顺序整理为 Markdown 文档。所有公式均使用标准 LaTeX 数学语法，并采用 `$$...$$` 块级公式格式，适合在 Typora、Obsidian、VS Code Markdown Preview Enhanced、支持 MathJax/KaTeX 的 Markdown 阅读器中渲染。

---

## 0. 阅读主线

论文提出的 **T-ALNS-RRD** 方法可以按公式体系理解为五个层次：

1. **DVRPTW-TA 问题建模**：公式 (1)–(7)，定义交通感知、带时间窗的动态车辆路径问题。
2. **交通流数据集成**：公式 (8)–(11)，将分时段交通速度、拥堵密度和不确定性引入路径成本。
3. **ALNS 全局搜索机制**：公式 (12)–(22)，通过破坏-修复、算子自适应和模拟退火进行全局优化。
4. **Tabu 记忆增强机制**：公式 (23)–(34)，通过禁忌记忆和频率记忆避免搜索循环并提升多样性。
5. **Rollout 实时调度机制**：公式 (35)–(44)，在突发交通事件、紧急订单等场景下进行短时域模拟决策。
6. **实验评价指标**：公式 (45)–(47)，定义准时率、平均路径时长和拥堵暴露分数。

---

## 1. 基础符号系统

### 1.1 网络与车辆

- $G=(N,A)$：有向配送网络。
- $N=\{0,1,2,\dots,n\}$：节点集合，其中 $0$ 表示仓库或配送中心，其余节点表示客户。
- $A\subseteq N\times N$：可行有向道路弧集合。
- $(i,j)$：从节点 $i$ 到节点 $j$ 的有向道路弧。
- $K=\{1,2,\dots,m\}$：车辆集合。
- $k$：车辆编号。
- $Q$：车辆容量。

### 1.2 客户属性

- $d_i$：客户 $i$ 的配送需求量。
- $s_i$：客户 $i$ 的服务时间。
- $[e_i,l_i]$：客户 $i$ 的服务时间窗。
- $e_i$：客户 $i$ 最早可开始服务时间。
- $l_i$：客户 $i$ 最晚可开始服务时间。

### 1.3 时间变量

- $A_i$：车辆到达客户 $i$ 的时间。
- $S_i$：车辆实际开始服务客户 $i$ 的时间。若早到，则需要等待到 $e_i$。
- $T_i=S_i+s_i$：车辆完成客户 $i$ 的服务并离开的时间。
- $t_{ij}(T_i)$：车辆在 $T_i$ 时刻从节点 $i$ 出发，经过弧 $(i,j)$ 所需的动态行驶时间。
- $\rho_{ij}(T_i)$：车辆在 $T_i$ 时刻经过弧 $(i,j)$ 的拥堵惩罚。
- $\delta_j$：客户 $j$ 的迟到惩罚。

### 1.4 决策变量

- $x_{ijk}\in\{0,1\}$：若车辆 $k$ 从节点 $i$ 直接行驶到节点 $j$，则 $x_{ijk}=1$；否则 $x_{ijk}=0$。

---

# 第一部分：DVRPTW-TA 问题建模

## 公式 (1)：综合目标函数

$$
\min
\sum_{k\in K}\sum_{(i,j)\in A}
x_{ijk}\left[t_{ij}(T_i)+\lambda_2\rho_{ij}(T_i)\right]
+\lambda_1\sum_{j\in N\setminus\{0\}}\delta_j
$$

### 变量说明

- $x_{ijk}$：车辆 $k$ 是否经过弧 $(i,j)$。
- $t_{ij}(T_i)$：车辆在 $T_i$ 时刻从节点 $i$ 到节点 $j$ 的行驶时间。
- $\rho_{ij}(T_i)$：对应道路弧的拥堵惩罚。
- $\delta_j$：客户 $j$ 的迟到惩罚。
- $\lambda_1$：迟到惩罚权重。
- $\lambda_2$：拥堵惩罚权重。

### 场景与解释

该目标函数是整篇论文的核心。它不是单纯最小化距离或行驶时间，而是同时最小化三类成本：

1. 车辆实际行驶时间；
2. 道路拥堵暴露程度；
3. 客户服务迟到惩罚。

因此，模型会倾向于选择既能节省时间、又能避开拥堵、同时尽量满足客户时间窗的配送路线。

---

## 公式 (2)：迟到惩罚定义

$$
\delta_j \equiv \max\{0, S_j-l_j\}
$$

### 变量说明

- $S_j$：客户 $j$ 的实际开始服务时间。
- $l_j$：客户 $j$ 的最晚服务时间。
- $\delta_j$：客户 $j$ 的迟到时间。

### 场景与解释

若 $S_j\le l_j$，说明车辆在客户允许时间窗内开始服务，则 $\delta_j=0$。若 $S_j>l_j$，说明迟到，迟到量为 $S_j-l_j$。

该公式说明论文采用的是 **软时间窗**：迟到不是完全不可行，但会被目标函数惩罚。

---

## 公式 (3)：每个客户必须被服务一次

$$
\sum_{k\in K}\sum_{j\in N}x_{ijk}=1,
\quad \forall i\in N\setminus\{0\}
$$

### 变量说明

- $i$：客户节点。
- $j$：客户 $i$ 之后可能访问的节点。
- $k$：车辆编号。
- $x_{ijk}$：车辆 $k$ 是否从客户 $i$ 行驶到节点 $j$。

### 场景与解释

该约束保证每个客户节点只被一辆车服务一次，不能漏送，也不能重复配送。

---

## 公式 (4)：车辆容量约束

$$
\sum_{i\in N\setminus\{0\}}d_i\sum_{j\in N}x_{ijk}\le Q,
\quad \forall k\in K
$$

### 变量说明

- $d_i$：客户 $i$ 的货物需求量。
- $Q$：车辆最大容量。
- $x_{ijk}$：车辆 $k$ 是否服务客户 $i$。

### 场景与解释

该公式约束每辆车服务的客户总需求不能超过车辆容量。例如车辆容量为 120 kg，则该车路线中所有客户需求之和不能超过 120 kg。

---

## 公式 (5)：时间递推与服务时间窗约束

$$
\text{if } x_{ijk}=1,\text{ then }
A_j\ge T_i+t_{ij}(T_i),
\quad
S_j\ge \max\{A_j,e_j\},
\quad
T_j=S_j+s_j
$$

### 变量说明

- $A_j$：车辆到达客户 $j$ 的时间。
- $T_i$：车辆离开客户 $i$ 的时间。
- $t_{ij}(T_i)$：从客户 $i$ 到客户 $j$ 的动态行驶时间。
- $S_j$：客户 $j$ 的开始服务时间。
- $e_j$：客户 $j$ 的最早服务时间。
- $s_j$：客户 $j$ 的服务时长。
- $T_j$：车辆离开客户 $j$ 的时间。

### 场景与解释

如果车辆从 $i$ 到 $j$，则到达 $j$ 的时间至少等于离开 $i$ 的时间加上路上行驶时间。若车辆早于客户最早服务时间到达，则需要等待。因此服务开始时间由到达时间和时间窗下界共同决定。

---

## 公式 (6)：软时间窗松弛变量

$$
S_j\le l_j+\epsilon_j,
\quad
\epsilon_j\ge 0
$$

等价地，

$$
\delta_j=\epsilon_j=\max\{0,S_j-l_j\}
$$

### 变量说明

- $S_j$：客户 $j$ 的开始服务时间。
- $l_j$：客户 $j$ 的最晚服务时间。
- $\epsilon_j$：时间窗松弛变量。
- $\delta_j$：迟到惩罚。

### 场景与解释

该公式允许车辆在特殊情况下晚于客户最晚服务时间开始服务，但晚到部分会转化为惩罚项进入目标函数。

---

## 公式 (7)：MTZ 子回路消除约束

$$
u_i-u_j+n\sum_{k\in K}x_{ijk}\le n-1,
\quad
\forall i\ne j,\ i,j\in N\setminus\{0\}
$$

### 变量说明

- $u_i,u_j$：客户访问顺序变量。
- $n$：客户数量。
- $x_{ijk}$：车辆 $k$ 是否从客户 $i$ 到客户 $j$。

### 场景与解释

车辆路径问题中可能出现不经过仓库的孤立客户循环，即子回路。该约束通过访问顺序变量限制路径结构，防止出现不合法的孤立回路。

---

# 第二部分：交通流数据集成

## 公式 (8)：分时段行驶时间赋值

$$
t_{ij}(T_i)=\acute{t}_{ij}^{(h)},
\quad \text{if } T_i\in\tau_h
$$

### 变量说明

- $\tau_h$：第 $h$ 个时间区间。
- $\acute{t}_{ij}^{(h)}$：道路弧 $(i,j)$ 在时间区间 $\tau_h$ 内的平均行驶时间。
- $T_i$：车辆从节点 $i$ 出发的时间。

### 场景与解释

城市道路行驶时间会随时段变化。该公式表示：如果车辆在时间段 $\tau_h$ 内出发，则使用该时间段对应的平均行驶时间作为弧 $(i,j)$ 的通行时间。

---

## 公式 (9)：拥堵惩罚计算

$$
\rho_{ij}(T_i)=\theta\cdot \gamma_{ij}^{(h)},
\quad \text{if } T_i\in\tau_h
$$

### 变量说明

- $\rho_{ij}(T_i)$：道路弧 $(i,j)$ 在 $T_i$ 时刻的拥堵惩罚。
- $\theta>0$：拥堵严重程度缩放系数。
- $\gamma_{ij}^{(h)}\in[0,1]$：时间段 $\tau_h$ 内道路弧 $(i,j)$ 的归一化交通密度。

### 场景与解释

即使两条路径行驶时间接近，算法也会倾向于避开交通密度更高的道路。该公式把交通密度转化为目标函数中的拥堵成本。

---

## 公式 (10)：考虑不确定性的调整行驶时间

$$
t'_{ij}(T_i)=\acute{t}_{ij}^{(h)}+\beta\cdot\eta_{ij}^{(h)},
\quad \text{if } T_i\in\tau_h
$$

### 变量说明

- $t'_{ij}(T_i)$：考虑不确定性后的行驶时间。
- $\eta_{ij}^{(h)}$：道路弧 $(i,j)$ 在时间段 $h$ 的行驶时间不确定性或可靠性裕度。
- $\beta\ge 0$：风险规避系数。

### 场景与解释

如果某条道路行驶时间波动较大，模型会在平均行驶时间基础上增加安全裕度。$\beta$ 越大，路径规划越保守，越倾向于避开不确定性高的道路。

---

## 公式 (11)：FIFO 一致性条件

$$
T_i^1\le T_i^2
\Rightarrow
T_i^1+t_{ij}(T_i^1)
\le
T_i^2+t_{ij}(T_i^2),
\quad \forall (i,j)\in A
$$

### 变量说明

- $T_i^1,T_i^2$：两个不同的出发时间，且 $T_i^1\le T_i^2$。
- $t_{ij}(T_i^1)$：早出发时的行驶时间。
- $t_{ij}(T_i^2)$：晚出发时的行驶时间。

### 场景与解释

FIFO 表示“先出发不应比后出发更晚到达”。该约束保证动态交通函数符合基本交通逻辑，避免出现不合理的时间悖论。

---

# 第三部分：ALNS 全局搜索机制

## 公式 (12)：车辆路径表示

$$
R_k=\langle 0,c_{k1},c_{k2},\dots,c_{k|R_k|},0\rangle
$$

### 变量说明

- $R_k$：车辆 $k$ 的配送路径。
- $0$：仓库或配送中心。
- $c_{ki}$：车辆 $k$ 服务的第 $i$ 个客户。
- $|R_k|$：车辆 $k$ 路径中的客户数量。

### 场景与解释

该公式表示每辆车从仓库出发，依次服务若干客户，最后返回仓库。例如 $R_1=\langle 0,1,3,5,0\rangle$ 表示车辆 1 依次服务客户 1、3、5。

---

## 公式 (13)：单条路径容量约束

$$
\sum_{i=1}^{|R_k|}d_{c_{ki}}\le Q
$$

### 变量说明

- $d_{c_{ki}}$：车辆 $k$ 路径中第 $i$ 个客户的需求量。
- $Q$：车辆容量。

### 场景与解释

这是容量约束在单条路径上的表达。它要求车辆 $k$ 路径中所有客户需求之和不超过车辆容量。

---

## 公式 (14)：Destroy-Repair 生成新解

$$
S'=R(D(S_t))
$$

### 变量说明

- $S_t$：第 $t$ 次迭代时的当前解。
- $D(\cdot)$：破坏算子，从当前解中移除部分客户。
- $R(\cdot)$：修复算子，将移除客户重新插入路线。
- $S'$：破坏-修复后得到的新候选解。

### 场景与解释

ALNS 的核心思想是先破坏当前解的一部分，再重新修复。这样可以跳出局部最优，探索新的路径结构。

---

## 公式 (15)：被移除客户数量

$$
|C|=\lfloor \alpha\cdot n\rfloor,
\quad \alpha\in[0.1,0.4]
$$

### 变量说明

- $C$：被破坏算子移除的客户集合。
- $|C|$：被移除客户数量。
- $n$：客户总数。
- $\alpha$：破坏比例。

### 场景与解释

该公式控制 ALNS 每次扰动的幅度。例如 $n=50$ 且 $\alpha=0.2$ 时，每次移除约 10 个客户再重新插入。

---

## 公式 (16)：局部插入成本

$$
\Delta f_{ijk}(T_j)
=
t_{ji}(T_j)+s_i
+t_{ik}\left(T_j+t_{ji}(T_j)+s_i\right)
-t_{jk}(T_j)
+\lambda_1\delta_i(T_i)
+\lambda_2\rho_{ji}(T_j)
$$

### 变量说明

- $\Delta f_{ijk}(T_j)$：将客户 $i$ 插入节点 $j$ 和节点 $k$ 之间的局部成本变化。
- $t_{ji}(T_j)$：从 $j$ 到 $i$ 的动态行驶时间。
- $s_i$：客户 $i$ 的服务时间。
- $t_{ik}(T_j+t_{ji}(T_j)+s_i)$：服务完客户 $i$ 后，从 $i$ 到 $k$ 的行驶时间。
- $t_{jk}(T_j)$：原路径中从 $j$ 直接到 $k$ 的行驶时间。
- $\delta_i(T_i)$：插入客户 $i$ 后可能产生的迟到惩罚。
- $\rho_{ji}(T_j)$：从 $j$ 到 $i$ 的拥堵惩罚。

### 场景与解释

该公式评估“把客户 $i$ 插入到 $j$ 和 $k$ 之间是否划算”。它比较原来的 $j\to k$ 与新路径 $j\to i\to k$ 的成本差，并加入服务时间、迟到惩罚和拥堵惩罚。

---

## 公式 (17)：完整插入成本变化

$$
\Delta F_{jik}
=
\Delta f_{jik}^{\mathrm{local}}(T_j)
+
\sum_{(u,v)\in \mathcal{A}_{\mathrm{suffix}}}
\left[
 t_{uv}(T'_u)
 +\lambda_1\delta_v(T'_v)
 +\lambda_2\rho_{uv}(T'_u)
\right]
-
\sum_{(u,v)\in \mathcal{A}^{\mathrm{old}}_{\mathrm{suffix}}}
\left[
 t_{uv}(T_u)
 +\lambda_1\delta_v(T_v)
 +\lambda_2\rho_{uv}(T_u)
\right]
$$

### 变量说明

- $\Delta F_{jik}$：完整边际插入成本变化。
- $\Delta f_{jik}^{\mathrm{local}}(T_j)$：局部插入成本。
- $\mathcal{A}_{\mathrm{suffix}}$：插入后受影响的后续路径弧集合。
- $\mathcal{A}^{\mathrm{old}}_{\mathrm{suffix}}$：插入前对应的后续路径弧集合。
- $T'_u,T'_v$：插入后重新前向传播得到的时间。
- $T_u,T_v$：插入前的原始时间。

### 场景与解释

公式 (16) 只考虑插入位置附近的直接变化，但在带时间窗的问题中，插入一个客户会影响后续所有客户的到达时间。因此公式 (17) 对受影响的后缀路径重新计算行驶时间、迟到惩罚和拥堵惩罚。

### 原文问题提示

论文原文公式 (17) 的旧后缀路径成本项存在排版异常，出现类似 $t_{uv}(T_u)(16\lambda')\delta_v(T_v)$ 的不合理连写。本文档按上下文将其规范化为“行驶时间 + 迟到惩罚 + 拥堵惩罚”的差分形式。

---

## 公式 (18)：算子选择概率

$$
p_h(t)=\frac{\omega_h(t)}{\sum_{j\in\mathcal{H}}\omega_j(t)}
$$

### 变量说明

- $h$：某个 destroy 或 repair 算子。
- $\mathcal{H}=\mathcal{D}\cup\mathcal{R}$：所有破坏算子和修复算子的集合。
- $\omega_h(t)$：算子 $h$ 在第 $t$ 次迭代时的权重。
- $p_h(t)$：算子 $h$ 被选中的概率。

### 场景与解释

ALNS 不固定使用某一个算子，而是根据历史表现动态调整算子选择概率。权重越高，算子越容易被选中。

---

## 公式 (19)：算子权重更新

$$
\omega_h(t+1)=(1-\xi)\omega_h(t)+\xi\theta_r
$$

### 变量说明

- $\omega_h(t)$：当前算子权重。
- $\omega_h(t+1)$：更新后的算子权重。
- $\xi\in(0,1)$：反应因子，控制对近期表现的敏感程度。
- $\theta_r$：本轮表现对应的奖励值。

### 场景与解释

若某个算子产生了更好的解，则给予较高奖励；若贡献较小，则奖励较低。该公式体现了 ALNS 的“自适应”机制。

---

## 公式 (20)：模拟退火接受准则

$$
P_{\mathrm{accept}}(S',S_t)=
\begin{cases}
1, & \text{if } f(S')<f(S_t),\\
\exp\left(-\dfrac{f(S')-f(S_t)}{\tau_t}\right), & \text{otherwise}.
\end{cases}
$$

### 变量说明

- $S'$：候选解。
- $S_t$：当前解。
- $f(S')$：候选解目标函数值。
- $f(S_t)$：当前解目标函数值。
- $\tau_t$：当前温度参数。

### 场景与解释

若候选解更优，则一定接受。若候选解更差，也可能以一定概率接受，从而帮助算法跳出局部最优。

---

## 公式 (21)：温度冷却

$$
\tau_{t+1}=\gamma\cdot\tau_t,
\quad \gamma\in(0,1)
$$

### 变量说明

- $\tau_t$：当前温度。
- $\tau_{t+1}$：下一轮温度。
- $\gamma$：冷却系数。

### 场景与解释

随着迭代进行，温度逐渐降低。算法早期更愿意探索，后期逐渐收敛。

---

## 公式 (22)：历史最优解

$$
S^*=\arg\min_{t\in[0,T_{\max}]} f(S_t)
$$

### 变量说明

- $S^*$：迭代过程中找到的最优解。
- $S_t$：第 $t$ 次迭代的解。
- $T_{\max}$：最大迭代次数。
- $f(S_t)$：解 $S_t$ 的目标函数值。

### 场景与解释

该公式从整个搜索历史中选择目标函数值最小的解作为最终输出。

---

# 第四部分：Tabu 记忆增强机制

## 公式 (23)：Move-based Tabu 判断

$$
|C_{\mathrm{removed}}\cap \acute{C}|
\ge
\mu\cdot\min\left(|C_{\mathrm{removed}}|,|\acute{C}|\right)
\quad \text{and}\quad
 t_{\mathrm{current}}-\acute{t}\le \tau_{\mathrm{move}}
$$

### 变量说明

- $C_{\mathrm{removed}}$：当前破坏操作移除的客户集合。
- $\acute{C}$：Tabu 记忆中已有的历史移除客户集合。
- $\mu\in[0,1]$：集合重叠阈值。
- $t_{\mathrm{current}}$：当前迭代次数。
- $\acute{t}$：历史操作发生的迭代次数。
- $\tau_{\mathrm{move}}$：move-based Tabu 禁忌期限。

### 场景与解释

如果当前破坏操作与近期某次操作高度相似，且仍处于禁忌期限内，则当前操作被视为 Tabu。这样可以防止算法反复执行相似的破坏-修复操作。

---

## 公式 (24)：Solution-based Hash 表示

$$
H(S)=
\sum_{k\in K}\sum_{i=1}^{p_k-1}
\varphi\left(v_{ki},v_{k(i+1)}\right)
\bmod P
$$

### 变量说明

- $H(S)$：解 $S$ 的哈希值。
- $v_{ki}$：车辆 $k$ 路径中第 $i$ 个节点。
- $p_k$：车辆 $k$ 路径中的节点数量。
- $\varphi(u,v)$：针对连续节点对 $(u,v)$ 的多项式哈希函数。
- $P$：较大的素数模数。

### 场景与解释

该公式把完整路径结构编码成哈希值。如果某个候选解的哈希值近期出现过，说明算法可能回到旧解，因此可以将其判定为 Tabu。

---

## 公式 (25)：客户-车辆分配频率更新

$$
F_{ik}^{\mathrm{cv}}(t+1)=
F_{ik}^{\mathrm{cv}}(t)
+\mathbf{1}_{[i\in R_k(S_{t+1})]}
$$

### 变量说明

- $F_{ik}^{\mathrm{cv}}$：客户 $i$ 被车辆 $k$ 服务的历史频率。
- $\mathbf{1}_{[\cdot]}$：指示函数，条件成立为 1，否则为 0。
- $R_k(S_{t+1})$：新解 $S_{t+1}$ 中车辆 $k$ 的路径。

### 场景与解释

该公式记录客户与车辆之间的分配频率。若某客户长期由同一辆车服务，频率会升高，算法后续可倾向于尝试低频组合以增加多样性。

---

## 公式 (26)：客户路径位置频率更新

$$
F_{ij}^{\mathrm{tp}}(t+1)=
F_{ij}^{\mathrm{tp}}(t)
+
\sum_{k\in K}\mathbf{1}_{[v_{kj}=i\ \text{in}\ S_{t+1}]}
$$

### 变量说明

- $F_{ij}^{\mathrm{tp}}$：客户 $i$ 出现在路径第 $j$ 个位置的频率。
- $v_{kj}$：车辆 $k$ 路径中第 $j$ 个节点。
- $S_{t+1}$：新解。

### 场景与解释

该公式记录客户在路径中不同位置出现的频率，用于鼓励算法尝试新的访问顺序。

---

## 公式 (27)：多样化强度指标

$$
\delta(t)=
\omega_1\frac{t-t_{\mathrm{last\_best}}}{T_{\max}}
+
\omega_2\frac{|T_{\mathrm{move}}|}{|T_{\mathrm{move}}|_{\max}}
+
\omega_3\sigma(F^{\mathrm{cv}})
$$

### 变量说明

- $\delta(t)$：搜索多样化或停滞程度指标。
- $t$：当前迭代次数。
- $t_{\mathrm{last\_best}}$：最近一次找到更优解的迭代次数。
- $T_{\max}$：最大迭代次数。
- $|T_{\mathrm{move}}|$：当前 move Tabu 列表长度。
- $|T_{\mathrm{move}}|_{\max}$：move Tabu 列表最大长度。
- $\sigma(F^{\mathrm{cv}})$：客户-车辆分配频率矩阵的标准差。
- $\omega_1,\omega_2,\omega_3$：权重，通常满足 $\omega_1+\omega_2+\omega_3=1$。

### 场景与解释

如果长时间没有找到更优解，且频率矩阵显示搜索集中于少数结构，则说明算法可能停滞，需要增强多样化。

### 符号提示

论文中 $\delta$ 同时用于迟到惩罚和多样化强度，复现代码时建议分别命名为 `lateness_delta` 和 `diversification_delta`。

---

## 公式 (28)：多样化调整后的算子选择概率

$$
p'_h(t)=
\eta p_h(t)
+
(1-\eta)
\frac{\mathrm{div}_h(t)}{\sum_{j\in\mathcal{H}}\mathrm{div}_j(t)}
$$

### 变量说明

- $p'_h(t)$：调整后的算子选择概率。
- $p_h(t)$：原始基于历史表现的算子选择概率。
- $\mathrm{div}_h(t)$：算子 $h$ 的多样化潜力。
- $\eta\in[0,1]$：性能导向与多样化导向之间的平衡系数。

### 场景与解释

当搜索陷入局部区域时，不能只依赖历史表现最好的算子，还需要增加能产生新结构的算子概率。该公式将“历史表现”和“多样化潜力”结合起来。

---

## 公式 (29)：全局最优特赦准则

$$
f(S')<f(S^*)
$$

### 变量说明

- $S'$：候选解。
- $S^*$：当前全局最优解。
- $f(\cdot)$：目标函数值。

### 场景与解释

即使某个动作被 Tabu 限制，只要它能产生比当前全局最优解更好的结果，就允许接受。这是 Tabu Search 中常见的 aspiration criterion。

---

## 公式 (30)：低频分配特赦准则

$$
\min_{i\in C_{\mathrm{removed}}}
\min_{k\in K}
F_{ik}^{\mathrm{cv}}
<
\beta\cdot \bar{F}^{\mathrm{cv}}
$$

### 变量说明

- $C_{\mathrm{removed}}$：当前被移除、等待重新插入的客户集合。
- $F_{ik}^{\mathrm{cv}}$：客户 $i$ 被车辆 $k$ 服务的历史频率。
- $\bar{F}^{\mathrm{cv}}$：客户-车辆分配频率均值。
- $\beta\in(0,1)$：低频阈值系数。

### 场景与解释

如果某个操作涉及很少尝试过的客户-车辆组合，即使它受到 Tabu 限制，也可以被接受。这有助于探索未充分搜索的解空间。

---

## 公式 (31)：交通适应性特赦准则

$$
\sum_{k\in K}\sum_{(i,j)\in A_k}
\lambda_2\rho_{ij}(T_i^k)
<
\gamma
\sum_{k\in K}\sum_{(i,j)\in A_k^{\mathrm{current}}}
\lambda_2\rho_{ij}(T_i^{k,\mathrm{current}})
$$

### 变量说明

- $A_k$：候选解中车辆 $k$ 经过的道路弧集合。
- $A_k^{\mathrm{current}}$：当前解中车辆 $k$ 经过的道路弧集合。
- $\rho_{ij}(T_i^k)$：候选路径的拥堵惩罚。
- $\rho_{ij}(T_i^{k,\mathrm{current}})$：当前路径的拥堵惩罚。
- $\lambda_2$：拥堵惩罚权重。
- $\gamma\in(0,1)$：拥堵改善阈值。

### 场景与解释

若某个候选解能够显著降低拥堵成本，即使它违反 Tabu，也可以被接受。这体现了论文的 traffic-aware 特征。

---

## 公式 (32)：Move Tabu 期限自适应更新

$$
\tau_{\mathrm{move}}(t+1)=
\begin{cases}
\min\left(\tau_{\mathrm{move}}(t)+1,\tau_{\max}\right),
& \text{若最近 }\tau_{\mathrm{stall}}\text{ 次迭代无改进},\\
\max\left(\tau_{\mathrm{move}}(t)-1,\tau_{\min}\right),
& \text{若找到改进}.
\end{cases}
$$

### 变量说明

- $\tau_{\mathrm{move}}(t)$：当前 move Tabu 期限。
- $\tau_{\max}$：最大 Tabu 期限。
- $\tau_{\min}$：最小 Tabu 期限。
- $\tau_{\mathrm{stall}}$：判断搜索停滞的迭代窗口。

### 场景与解释

若算法长期没有改进，则增加禁忌期限，迫使搜索离开近期区域；若找到改进，则缩短禁忌期限，使搜索可以更集中地开发优质区域。

---

## 公式 (33)：频率矩阵归一化

$$
F_{ik}^{\mathrm{cv}}
\leftarrow
\left\lfloor \frac{F_{ik}^{\mathrm{cv}}}{\kappa}\right\rfloor
\quad \text{every }\nu\text{ iterations}
$$

### 变量说明

- $F_{ik}^{\mathrm{cv}}$：客户-车辆分配频率。
- $\kappa>1$：归一化缩放因子。
- $\nu$：归一化执行周期。

### 场景与解释

频率矩阵会随迭代不断累积。该公式定期缩小频率数值，避免数值过大，同时保留相对频率信息。

---

## 公式 (34)：拥堵加权频率记忆

$$
F_{ik}^{\mathrm{cv}}(t+1)=
F_{ik}^{\mathrm{cv}}(t)
+
\mathbf{1}_{[i\in R_k(S_{t+1})]}
\cdot
\left(
1+
\sum_{j:(j,i)\in A_k}
\rho_{ji}(T_j^k)
\right)
$$

### 变量说明

- $F_{ik}^{\mathrm{cv}}$：客户 $i$ 与车辆 $k$ 的分配频率。
- $R_k(S_{t+1})$：新解中车辆 $k$ 的路径。
- $(j,i)\in A_k$：车辆 $k$ 到达客户 $i$ 之前经过的入弧。
- $\rho_{ji}(T_j^k)$：从 $j$ 到 $i$ 的拥堵惩罚。

### 场景与解释

如果某个客户-车辆组合经常伴随高拥堵路径，则该组合的频率会更快累积，促使算法在后续搜索中尝试其他车辆或其他路径。

---

# 第五部分：Rollout 实时调度机制

## 公式 (35)：事件紧急度评分

$$
\Psi(e,t)=
\alpha_e\frac{t_{\mathrm{deadline}}-t_{\mathrm{current}}}{t_{\mathrm{horizon}}}
+
\beta_e\,\mathrm{impact}(e)
+
\gamma_e\,\mathrm{cost\_increase}(e)
$$

### 变量说明

- $\Psi(e,t)$：事件 $e$ 在时间 $t$ 的紧急度评分。
- $e$：实时事件，例如交通事故、紧急订单、容量冲突、时间窗风险。
- $\alpha_e,\beta_e,\gamma_e$：事件类型相关权重。
- $t_{\mathrm{deadline}}$：事件相关约束的截止时间。
- $t_{\mathrm{current}}$：当前时间。
- $t_{\mathrm{horizon}}$：规划时间范围。
- $\mathrm{impact}(e)$：事件影响范围。
- $\mathrm{cost\_increase}(e)$：若不处理事件可能导致的成本增加。

### 场景与解释

该公式用于判断是否触发实时调度。突发事件影响越大、潜在成本越高，越可能触发 RRD 模块。

### 复现提示

如果 $\Psi(e,t)$ 被设定为“越大越紧急”，则第一项 $\frac{t_{\mathrm{deadline}}-t_{\mathrm{current}}}{t_{\mathrm{horizon}}}$ 在直觉上可能方向相反，因为剩余时间越少，该项越小。复现时建议核查作者代码或考虑改为 $1-\frac{t_{\mathrm{deadline}}-t_{\mathrm{current}}}{t_{\mathrm{horizon}}}$。

---

## 公式 (36)：Rollout 价值函数

$$
V^{\mathrm{rollout}}(s,a,H)=
\mathbb{E}\left[
\sum_{h=0}^{H-1}
\left(
\sum_{k\in K}\sum_{(i,j)\in A_k^h}
\left[
 t_{ij}(T_i^{k,h})
 +\lambda_2\rho_{ij}(T_i^{k,h})
\right]
+
\lambda_1\sum_{j\in C^h}\delta_j(S_j^h)
\right)
\right]
$$

### 变量说明

- $V^{\mathrm{rollout}}(s,a,H)$：状态 $s$ 下执行动作 $a$ 并向前模拟 $H$ 步后的期望成本。
- $s$：当前系统状态。
- $a$：候选调度动作。
- $H$：Rollout 模拟时域。
- $\mathbb{E}[\cdot]$：对未来交通与事件不确定性的期望。
- $h$：模拟步。
- $A_k^h$：第 $h$ 步中车辆 $k$ 经过的道路弧集合。
- $T_i^{k,h}$：第 $h$ 步中车辆 $k$ 从节点 $i$ 出发的时间。
- $C^h$：第 $h$ 步中开始服务的客户集合。
- $S_j^h$：第 $h$ 步客户 $j$ 的开始服务时间。

### 场景与解释

当突发事件发生后，系统对多个候选动作进行短时域模拟，估计每个动作在未来一段时间内可能产生的行驶时间、拥堵惩罚和迟到惩罚。

---

## 公式 (37)：候选动作可行性检查

$$
\mathrm{Feasible}(a,s)=
\bigwedge_{k\in K}
\left[
\sum_{i\in R_k^a}d_i\le Q
\right]
\wedge
\bigwedge_{i\in N^a}
\left[
 e_i\le T_i^a\le l_i+\epsilon_{\mathrm{tolerance}}
\right]
$$

### 变量说明

- $\mathrm{Feasible}(a,s)$：动作 $a$ 在状态 $s$ 下是否可行。
- $\bigwedge$：逻辑“且”。
- $R_k^a$：执行动作 $a$ 后车辆 $k$ 服务的客户集合。
- $N^a$：执行动作 $a$ 后被服务的客户集合。
- $T_i^a$：执行动作 $a$ 后客户 $i$ 的预计服务时间。
- $\epsilon_{\mathrm{tolerance}}$：紧急情况下允许的时间窗松弛量。

### 场景与解释

并非所有实时调度动作都能执行。例如把客户转给另一辆车时，必须同时检查车辆是否超载，以及客户时间窗是否仍可接受。

---

## 公式 (38)：Rollout 短时交通插值

$$
t_{ij}^{\mathrm{rollout}}(T_i+s)=
\acute{t}_{ij}^{(r)}
+
\frac{s}{\Delta t}
\left(
\acute{t}_{ij}^{(r+1)}-\acute{t}_{ij}^{(r)}
\right)
$$

### 变量说明

- $t_{ij}^{\mathrm{rollout}}(T_i+s)$：Rollout 中预测的短时行驶时间。
- $T_i$：车辆从节点 $i$ 出发的基准时间。
- $s$：从当前时间向前推进的偏移量。
- $\Delta t$：交通时间离散间隔。
- $\acute{t}_{ij}^{(r)}$：第 $r$ 个时间段的平均行驶时间。
- $\acute{t}_{ij}^{(r+1)}$：下一时间段的平均行驶时间。

### 场景与解释

全局路径优化中使用分段常数交通时间，但实时调度需要更平滑的短时预测。因此该公式用线性插值估计未来短时段内的道路行驶时间。

---

## 公式 (39)：Tabu 调整后的 Rollout 价值

$$
V^{\mathrm{adjusted}}(s,a,H)=
V^{\mathrm{rollout}}(s,a,H)
-
\tau_{\mathrm{penalty}}\cdot\mathbf{1}_{[\mathrm{Tabu}(a)]}
+
\tau_{\mathrm{bonus}}\cdot\mathrm{Diversification}(a)
$$

### 变量说明

- $V^{\mathrm{adjusted}}(s,a,H)$：Tabu 记忆调整后的 Rollout 价值。
- $V^{\mathrm{rollout}}(s,a,H)$：原始 Rollout 价值。
- $\mathbf{1}_{[\mathrm{Tabu}(a)]}$：动作 $a$ 是否违反 Tabu 限制的指示函数。
- $\tau_{\mathrm{penalty}}$：Tabu 违规惩罚系数。
- $\tau_{\mathrm{bonus}}$：多样化奖励系数。
- $\mathrm{Diversification}(a)$：动作 $a$ 对搜索多样性的贡献。

### 场景与解释

实时调度不仅考虑短期成本，还要考虑是否重复近期不推荐的动作，以及是否能促进路径结构多样化。

### 复现提示

若 $V$ 被作为“成本”并需要最小化，则 Tabu 惩罚通常应增加成本，而原文采用减号形式。复现时应核查作者的评分方向：若最终是最大化评分，则该符号可以解释；若最终是最小化成本，则建议将 Tabu 惩罚项改为加号。

---

## 公式 (40)：最终调度综合评分

$$
\Sigma(a,e,s)=
\omega_1V^{\mathrm{adjusted}}(s,a,H)
+
\omega_2\mathrm{Stability}(a,s)
+
\omega_3\mathrm{Recovery}(a,s)
$$

### 变量说明

- $\Sigma(a,e,s)$：动作 $a$ 面向事件 $e$ 和状态 $s$ 的综合评分。
- $V^{\mathrm{adjusted}}(s,a,H)$：调整后的 Rollout 价值。
- $\mathrm{Stability}(a,s)$：路径稳定性。
- $\mathrm{Recovery}(a,s)$：恢复性。
- $\omega_1,\omega_2,\omega_3$：三项评分权重。

### 场景与解释

最终动作选择不仅考虑短期成本，还考虑是否尽量少破坏原路径，以及是否便于系统恢复到更优路径结构。

---

## 公式 (41)：路径稳定性

$$
\mathrm{Stability}(a,s)=
\sum_{k\in K}
\frac{|R_k^a\cap R_k^s|}{|R_k^a\cup R_k^s|}
$$

### 变量说明

- $R_k^a$：执行动作 $a$ 后车辆 $k$ 的客户集合。
- $R_k^s$：当前状态 $s$ 下车辆 $k$ 的客户集合。
- $\cap$：集合交集。
- $\cup$：集合并集。

### 场景与解释

该公式类似 Jaccard 相似度，用于衡量调度前后车辆路径结构是否保持稳定。调整越少，稳定性越高。

---

## 公式 (42)：恢复性指标

$$
\mathrm{Recovery}(a,s)=
-
\sum_{k\in K}\sum_{i\in R_k^a}
\left|
\mathrm{OptimalPosition}(i)-\mathrm{CurrentPosition}(i,a)
\right|
$$

### 变量说明

- $\mathrm{Recovery}(a,s)$：动作 $a$ 的恢复性得分。
- $\mathrm{OptimalPosition}(i)$：客户 $i$ 在最近一次 T-ALNS 优化解中的位置。
- $\mathrm{CurrentPosition}(i,a)$：执行动作 $a$ 后客户 $i$ 的当前位置。
- $R_k^a$：动作 $a$ 后车辆 $k$ 的客户集合。

### 场景与解释

如果实时调度动作使客户顺序严重偏离原优化路径，则恢复性得分降低。前面的负号表示偏离越大，得分越低。

---

## 公式 (43)：Rollout 时域自适应

$$
H_{\mathrm{rollout}}=
\max\left(
H_{\min},
H_{\max}-\alpha_{\mathrm{urgency}}\Psi(e,t)
\right)
$$

### 变量说明

- $H_{\mathrm{rollout}}$：实时调度使用的 Rollout 模拟时域。
- $H_{\min}$：最短模拟时域。
- $H_{\max}$：最长模拟时域。
- $\alpha_{\mathrm{urgency}}$：紧急度对模拟时域的压缩系数。
- $\Psi(e,t)$：事件紧急度评分。

### 场景与解释

事件越紧急，系统越不能花太多时间做长时域模拟，因此 Rollout 时域随紧急度提高而缩短。

---

## 公式 (44)：Rollout 模拟次数自适应

$$
N_{\mathrm{sim}}=
\max\left(
N_{\min},
\left\lfloor
\frac{T_{\mathrm{available}}-T_{\mathrm{overhead}}}{T_{\mathrm{sim}}}
\right\rfloor
\right)
$$

### 变量说明

- $N_{\mathrm{sim}}$：可执行的 Rollout 模拟次数。
- $N_{\min}$：最小模拟次数。
- $T_{\mathrm{available}}$：当前可用于决策的时间预算。
- $T_{\mathrm{overhead}}$：调度系统固定开销时间。
- $T_{\mathrm{sim}}$：单次 Rollout 模拟耗时。
- $\lfloor\cdot\rfloor$：向下取整。

### 场景与解释

该公式根据实时计算资源决定模拟次数。可用时间越多，可以进行更多模拟；时间紧张时，也至少保证 $N_{\min}$ 次模拟。

### 复现提示

该公式只有下界，没有上界。实际实现时建议增加 $N_{\max}$：

$$
N_{\mathrm{sim}}=
\min\left(
N_{\max},
\max\left(
N_{\min},
\left\lfloor
\frac{T_{\mathrm{available}}-T_{\mathrm{overhead}}}{T_{\mathrm{sim}}}
\right\rfloor
\right)
\right)
$$

---

# 第六部分：实验评价指标公式

## 公式 (45)：准时配送率 OTDR

$$
\mathrm{OTDR}=\frac{N_{\mathrm{ontime}}}{|N\setminus\{0\}|}
$$

### 变量说明

- $\mathrm{OTDR}$：On-Time Delivery Ratio，即准时配送率。
- $N_{\mathrm{ontime}}$：在服务时间窗内完成服务的客户数量。
- $|N\setminus\{0\}|$：客户总数，不包括仓库节点。

### 场景与解释

该指标衡量客户时间窗满足程度。值越高，说明越多客户被准时服务。论文用该指标评估服务可靠性。

---

## 公式 (46)：平均路径持续时间

$$
\mathrm{AvgRouteDuration}=\frac{1}{|K|}
\sum_{k\in K}
\left(T_k^{\mathrm{end}}-T_k^{\mathrm{start}}\right)
$$

### 变量说明

- $\mathrm{AvgRouteDuration}$：平均路径持续时间。
- $|K|$：车辆数量。
- $T_k^{\mathrm{start}}$：车辆 $k$ 的出发时间。
- $T_k^{\mathrm{end}}$：车辆 $k$ 返回或完成路径的时间。

### 场景与解释

该指标衡量车辆路线从出发到结束的平均耗时，用于评价车辆使用效率和路线时间效率。

---

## 公式 (47)：拥堵暴露分数 CES

$$
\mathrm{CES}=\sum_{k\in K}\sum_{(i,j)\in A_k}
\rho_{ij}(T_i^k)
$$

### 变量说明

- $\mathrm{CES}$：Congestion Exposure Score，即拥堵暴露分数。
- $A_k$：车辆 $k$ 实际经过的道路弧集合。
- $\rho_{ij}(T_i^k)$：车辆 $k$ 在 $T_i^k$ 时刻经过弧 $(i,j)$ 的拥堵惩罚。

### 场景与解释

CES 越低，说明路径越能避开拥堵道路。该指标直接反映算法的 traffic-aware 能力。

---

# 第七部分：公式体系递进关系总结

## 7.1 从路径优化到交通感知路径优化

公式 (1)–(7) 将末端配送建模为带容量约束、时间窗约束和动态交通成本的车辆路径问题。相比经典 VRPTW，论文在目标函数中显式加入了时间依赖行驶时间 $t_{ij}(T_i)$ 和拥堵惩罚 $\rho_{ij}(T_i)$。

## 7.2 从静态交通成本到动态交通矩阵

公式 (8)–(11) 将交通流数据转化为路径优化可使用的动态成本。不同时间段对应不同道路行驶时间、拥堵惩罚和可靠性裕度，并用 FIFO 条件保证交通函数合理。

## 7.3 从数学模型到 ALNS 求解器

公式 (12)–(22) 描述 ALNS 如何表示路径、构造新解、计算插入成本、动态选择算子、更新算子权重并接受候选解。核心思想是通过 destroy-repair 不断改进路径结构。

## 7.4 从普通 ALNS 到 Tabu-ALNS

公式 (23)–(34) 引入多层 Tabu 记忆。Move-based Tabu 防止重复操作，solution-based Tabu 防止回到历史解，frequency-based memory 鼓励低频组合和路径结构探索，拥堵加权频率进一步强化避堵导向。

## 7.5 从离线路径优化到实时调度

公式 (35)–(44) 让算法具备实时响应能力。当交通事故、紧急订单、容量冲突或时间窗风险出现时，系统通过事件紧急度、可行动作集合、Rollout 模拟和综合评分选择响应动作。

## 7.6 从算法设计到实验评价

公式 (45)–(47) 给出实验评价指标。OTDR 衡量准时服务能力，AvgRouteDuration 衡量路径时间效率，CES 衡量拥堵规避能力。

---

# 第八部分：复现和阅读时需要注意的公式问题

## 8.1 公式编号存在局部错位

论文正文中部分文字引用的公式编号与实际公式编号不一致。例如，实时调度部分有多处将公式 (35) 写成公式 (34)，将公式 (37) 写成公式 (36)，将公式 (38) 写成公式 (37)。阅读时应以公式实际编号为准。

## 8.2 公式 (17) 存在排版异常

公式 (17) 的旧后缀路径成本项疑似排版错误。复现时建议使用本文档中的规范化版本。

## 8.3 公式 (35) 的紧急度方向需要核查

若 $\Psi(e,t)$ 越大表示越紧急，则剩余时间项的方向可能与直觉不一致。复现时建议核查原始代码或重新定义该项。

## 8.4 公式 (39) 的符号方向需要核查

若 $V^{\mathrm{rollout}}$ 是需要最小化的成本，则 Tabu 惩罚项应增加成本，而不是减少成本。论文原公式采用减号，可能意味着其最终评分是最大化型，也可能是符号书写问题。

## 8.5 符号复用较多

论文中多个符号存在复用：

- $\delta_j$：迟到惩罚；
- $\delta(t)$：多样化强度；
- $\beta$：既表示风险规避系数，也表示低频阈值；
- $\gamma$：既表示温度冷却系数，也表示拥堵改善阈值。

复现代码时建议使用更明确的变量名，例如：

- `lateness_delta`
- `diversification_delta`
- `risk_beta`
- `frequency_beta`
- `cooling_gamma`
- `traffic_improvement_gamma`

---

# 第九部分：一句话理解整篇论文公式体系

这篇论文的公式体系可以概括为：先用动态交通成本和软时间窗建立 DVRPTW-TA 优化模型，再用 ALNS 进行全局路径搜索，用多层 Tabu 记忆提升搜索稳定性和多样性，最后用 Rollout 机制在突发事件发生时快速模拟候选调度动作，从而实现动态城市末端配送的实时优化。
