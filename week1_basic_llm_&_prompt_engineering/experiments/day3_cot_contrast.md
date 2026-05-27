# DAY 3: CoT 对比实验

本实验对比有无CoT时模型解决算法题的回答。

## 实验配置

- **模型**：`deepseek chat`
- **问题**：Question: Given an integer array nums, return all the triplets [nums[i], nums[j], nums[k]] such that i != j, i != k, and j != k, and nums[i] + nums[j] + nums[k] == 0. Notice that the solution set must not contain duplicate triplets.

## 实验内容和结果

🔬 **实验组: 无 CoT**

模型回答：
这是一个经典的“三数之和”问题，要求找出所有不重复的三元组，其和为0。

**解题思路：**

1. 首先对数组排序，这样方便使用双指针法。
2. 固定一个数 `nums[i]`，然后使用双指针在剩余部分寻找两个数，使得三数之和为0。
3. 注意去重：当 `i` 移动时，如果 `nums[i] == nums[i-1]` 则跳过，避免重复三元组；双指针移动时也要跳过重复值。
4. 时间复杂度 O(n²)，空间复杂度 O(1)（不计输出空间）。

以下是完整的 Python 代码：

```python
class Solution:
    def threeSum(self, nums):
        nums.sort()
        result = []
        n = len(nums)

        for i in range(n - 2):
            # 剪枝：如果当前数大于0，后面全是正数，和不可能为0
            if nums[i] > 0:
                break
            # 跳过重复的 i
            if i > 0 and nums[i] == nums[i - 1]:
                continue

            left, right = i + 1, n - 1
            while left < right:
                total = nums[i] + nums[left] + nums[right]
                if total == 0:
                    result.append([nums[i], nums[left], nums[right]])
                    # 跳过重复的 left
                    while left < right and nums[left] == nums[left + 1]:
                        left += 1
                    # 跳过重复的 right
                    while left < right and nums[right] == nums[right - 1]:
                        right -= 1
                    left += 1
                    right -= 1
                elif total < 0:
                    left += 1
                else:
                    right -= 1

        return result
```

**示例运行：**

```python
sol = Solution()
print(sol.threeSum([-1, 0, 1, 2, -1, -4]))
# 输出: [[-1, -1, 2], [-1, 0, 1]]
```

---

🔬 **实验组: 有 CoT**

模型回答：
好的，我们来分析一下这个问题。这是一个经典的三数之和问题，相比两数之和要复杂不少，主要在于要去重并且优化时间复杂度到 O(n²)。

**思路分析：**

1. **暴力法不可取**  
   用三层循环会达到 O(n³)，肯定超时，所以必须优化。

2. **排序 + 双指针**  
   排序的复杂度是 O(n log n)，双指针扫描可以做到 O(n²)，整体可行。  
   关键在于：
   - 遍历固定第一个数 `nums[i]`。
   - 对每个 `i`，用双指针 `left = i + 1`, `right = n - 1` 在剩余部分寻找和为 `-nums[i]` 的两个数。
   - 找到一个三元组后，要跳过重复的元素，避免结果集重复。

3. **去重策略**
   - 如果 `nums[i]` 和上一个相同，跳过。
   - 找到三元组后，移动 `left` 和 `right` 时，也要分别跳过重复值。

4. **边界和剪枝**
   - 排序后，如果 `nums[i] > 0`，则三数和不可能为0，直接结束循环。
   - `nums[i]` 与后两个最小值的和如果 > 0，也可以终止。

---

**Python 代码实现：**

```python
from typing import List

class Solution:
    def threeSum(self, nums: List[int]) -> List[List[int]]:
        nums.sort()
        n = len(nums)
        result = []

        for i in range(n):
            # 如果第一个数已经大于0，后面的和不可能为0
            if nums[i] > 0:
                break
            # 跳过重复的第一个数
            if i > 0 and nums[i] == nums[i-1]:
                continue

            left, right = i + 1, n - 1
            target = -nums[i]

            while left < right:
                total = nums[left] + nums[right]
                if total < target:
                    left += 1
                elif total > target:
                    right -= 1
                else:
                    # 找到一个三元组
                    result.append([nums[i], nums[left], nums[right]])
                    # 跳过重复的第二个数
                    while left < right and nums[left] == nums[left + 1]:
                        left += 1
                    # 跳过重复的第三个数
                    while left < right and nums[right] == nums[right - 1]:
                        right -= 1
                    # 移动指针，继续寻找其他组合
                    left += 1
                    right -= 1

        return result
```

---

**复杂度分析：**

- **时间复杂度：** O(n²)  
  排序 O(n log n)，双指针扫描 O(n²)，整体为 O(n²)。
- **空间复杂度：** O(1) 或 O(n)（取决于排序实现），不计输出结果的空间。

这样就能正确、高效地返回所有不重复的三元组了。

---

## 实验结论与深度分析

通过对比 DeepSeek 在面对经典高频算法题（3Sum）时，有无 CoT (Chain of Thought) 提示词的表现差异，我们可以得出以下工程实践维度的核心结论：

### 1. 输出范式对比

| 评估维度       | 🔬 无 CoT (Zero-Shot)                  | 🔬 有 CoT (Few-Shot)                                                                          |
| :------------- | :------------------------------------- | :-------------------------------------------------------------------------------------------- |
| **破题切入点** | 直接输出解题步骤和最终代码             | **先破后立**：主动指出 $O(n^3)$ 暴力法的性能瓶颈，再引出优化路径                              |
| **思维结构**   | 偏向于“代码注释”的自然语言化           | 展现了严密的**工程推导流**：分析 $\rightarrow$ 降维 $\rightarrow$ 去重 $\rightarrow$ 边界剪枝 |
| **健壮性考量** | 隐式包含在代码逻辑中（直接写在循环内） | **显式剥离**：将边界条件（如 `nums[i] > 0` 的提前终止）作为独立逻辑块重点讨论                 |
| **代码规范度** | 标准的 Python 脚本解法                 | 自动引入 `from typing import List`，类型提示更契合现代工业级开发规范                          |

### 2. 核心实验洞察

- **从“代码生成器”到“系统工程师”的跨越**
  在未注入思维链时，模型表现得更像一个凭借肌肉记忆吐出答案的纯粹编码者，只关注结果本身。而引入了精心设计的 Few-Shot CoT 后，模型的输出高度还原了真实研发面试场上的高质沟通范式：优先探讨时空复杂度的权衡，明确边界防御条件，最后再落实到底层代码的实现。这种先理清底层逻辑再动手写代码的结构，正是区分基础执行者与具备深度系统化思考工程师的分水岭。
- **Few-Shot 模板的强大锚定效应**
  实验强有力地证明了，高质量的上下文示例能够直接重塑语言模型的状态机。我们在 Prompt 中为 `Two Sum` 构建的推导结构（痛点分析 $\rightarrow$ 数据结构优化 $\rightarrow$ 复杂度计算），被模型完美地平移到了复杂度更高的 `3Sum` 题目上。模型不仅成功进行了逻辑上的举一反三，甚至在代码的 Type Hinting 细节上也自动向更严谨的规范靠拢。
- **CoT 策略对逻辑死角的防御**
  对于 3Sum 这种极其容易在“多指针去重（Deduplication）”环节出现死循环或漏判的题目，强制要求模型先在 `Thought` 阶段用自然语言理清双指针的跳跃逻辑，相当于在正式编码前做了一次伪代码级别的 Code Review，极大地增强了最终算法应对复杂边缘测试用例时的鲁棒性。

**最终总结**：在解决具有复杂状态转移或多层逻辑嵌套的工程难题时，赋予模型 CoT 能力并非单纯为了获取“更长”的回答，而是为了获得具备**推导可回溯性**和**防御性编程思维**的高质量技术方案。
