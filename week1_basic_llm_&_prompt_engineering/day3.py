from llm import ask_llm
from textwrap import dedent

# llm arguments
temperature = 1

sys_prompt = "你一个专业的算法工程师，用Python解决算法题，并始终使用中文"

user_prompt = "Question: Given an integer array nums, return all the triplets [nums[i], nums[j], nums[k]] such that i != j, i != k, and j != k, and nums[i] + nums[j] + nums[k] == 0. Notice that the solution set must not contain duplicate triplets.\n\nThought:\n\nAnswer:\n\n"

cot_prompt = """
Question:
Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.

You may assume that each input would have exactly one solution, and you may not use the same element twice.

You can return the answer in any order.

Thought:
One brute force approach is to consider every pair of elements and check if their sum equals the target. This can be done using nested loops, where the outer loop iterates from the first element to the second-to-last element, and the inner loop iterates from the next element to the last element. However, this approach has a time complexity of O(n^2).
A more efficient approach is to use a hash table (unordered_map in C++). We can iterate through the array once, and for each element, check if the target minus the current element exists in the hash table. If it does, we have found a valid pair of numbers. If not, we add the current element to the hash table.
Approach using a hash table:

Create an empty hash table to store elements and their indices.
Iterate through the array from left to right.
For each element nums[i], calculate the complement by subtracting it from the target: complement = target - nums[i].
Check if the complement exists in the hash table. If it does, we have found a solution.
If the complement does not exist in the hash table, add the current element nums[i] to the hash table with its index as the value.
Repeat steps 3-5 until we find a solution or reach the end of the array.
If no solution is found, return an empty array or an appropriate indicator\n\n.

Answer:
```
class Solution:
    def twoSum(self, nums: List[int], target: int) -> List[int]:
        numMap = {}
        n = len(nums)

        for i in range(n):
            complement = target - nums[i]
            if complement in numMap:
                return [numMap[complement], i]
            numMap[nums[i]] = i

        return []  # No solution found
```
"""

# 无 CoT 解决算法题
print(f"实验：无 CoT ...")
ans_no_cot = ask_llm(sys_prompt, user_prompt, temperature)

# 有 CoT 解决算法题
print(f"实验：有 CoT ...")
ans_with_cot = ask_llm(sys_prompt, cot_prompt + user_prompt, temperature)

with open("experiments/day3_cot_contrast.md", "w", encoding="utf-8") as f:
  # metadata
  metadata = dedent("""
    # DAY 3: CoT 对比实验
    本实验对比有无CoT时模型解决算法题的回答。
    
    ## 实验配置
    
    - **模型**：`deepseek chat`
    - **问题**：Question: Given an integer array nums, return all the triplets [nums[i], nums[j], nums[k]] such that i != j, i != k, and j != k, and nums[i] + nums[j] + nums[k] == 0. Notice that the solution set must not contain duplicate triplets.
    
    ## 实验内容和结果\n\n
  """)
  f.write(metadata)
  
  # 记录实验结果
  f.write("🔬 **实验组: 无 CoT**\n\n")
  f.write(f"模型回答：\n")
  f.write(f"{ans_no_cot}\n\n")
  f.write(" \n---\n\n") # 加上分割线区分不同实验组
  
  f.write("🔬 **实验组: 有 CoT**\n\n")
  f.write(f"模型回答：\n")
  f.write(f"{ans_with_cot}\n\n")
  f.write(" \n---\n\n")
  
print("🎉 所有参数组合实验完毕！结果已汇总保存至 experiments/day3_cot_contrast.md")