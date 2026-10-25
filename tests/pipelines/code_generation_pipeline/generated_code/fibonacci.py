from typing import Dict

def fibonacci(n: int, memo: Dict[int, int] = None) -> int:
    """
    Calculate the nth Fibonacci number using memoization.

    Args:
        n (int): The position in the Fibonacci sequence to calculate. Must be a non-negative integer.
        memo (Dict[int, int], optional): A dictionary to store previously calculated Fibonacci numbers.
                                         Defaults to None, which initializes an empty dictionary.

    Returns:
        int: The nth Fibonacci number.

    Raises:
        ValueError: If the input n is a negative integer.
    """
    if memo is None:
        memo = {}
    
    if n < 0:
        raise ValueError("Input must be a non-negative integer.")
    
    if n in memo:
        return memo[n]
    
    if n == 0:
        return 0
    elif n == 1:
        return 1
    else:
        memo[n] = fibonacci(n - 1, memo) + fibonacci(n - 2, memo)
        return memo[n]