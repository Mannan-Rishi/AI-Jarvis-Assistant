try:
    import torch
    print(f"Torch version: {torch.__version__}")
    print("Success: Torch imported correctly.")
    
    print("Testing Tensor operation...")
    x = torch.rand(5, 3)
    print(x)
    print("Success: Tensor operation completed.")
    
except Exception as e:
    print(f"Failed: {e}")
    import traceback
    traceback.print_exc()
