import numpy as np

class GazeProcessor(object):
    
    def __init__(self, N, px_thresh):
        self.px_thresh = px_thresh
        self.bufflen = N
        self.curr_buffer = np.zeros((N,2))
        self.curr_buffer_n = 0
        self.curr_x = self.curr_y = float('nan')
        self.potential_x = self.potential_y = float('nan')
        self.potential_n = 0
        self.weights = np.arange(1,N+1) # weights for one-sided triangular window
        
        self.new_fixation = False        

    def process_dataframe(self, df):
        
        fixation_x = np.empty(len(df))
        fixation_y = np.empty(len(df))    
    
        # For each frame
        for i in range(len(df)):
            # get "new" x, y
            x = df['raw_x'][i]
            y = df['raw_y'][i]
            # Save result of simulated real-time algorithm
            (fixation_x[i], fixation_y[i]) = self.process_frame(x,y)
        
        return (fixation_x, fixation_y)

    def process_frame(self, x, y):
        # get current fixation position                
        distance = np.linalg.norm([self.curr_x-x, self.curr_y-y])
        self.new_fixation = False                        
        if distance < self.px_thresh:
            # Close to current. Clear potential slot
            self.potential_n = 0
            
            # Add to buffer
            self.curr_buffer = np.roll(self.curr_buffer,-1, axis=0)
            self.curr_buffer[-1] = (x,y)
            self.curr_buffer_n = min(self.curr_buffer_n+1, self.bufflen)
            
        else:
            # It's far away - check if close to previous potential window
            distance = np.linalg.norm([self.potential_x-x, self.potential_y-y])
            if self.potential_n > 0 and distance < self.px_thresh:
                    # Continues the last outlier. A new fixation!
                    self.new_fixation = True
                    self.potential_n = 0
                    self.curr_buffer_n = 2
                    self.curr_buffer[-2] = (self.potential_x,self.potential_y)
                    self.curr_buffer[-1] = (x,y)
            else:
                # Not close to current or potential position - save in potential
                self.potential_n = 1
                (self.potential_x, self.potential_y) = (x,y)
                
        # Calculate new fixation position average
        (self.curr_x, self.curr_y) = self.weights[-self.curr_buffer_n:].dot(self.curr_buffer[-self.curr_buffer_n:])/sum(self.weights[-self.curr_buffer_n:])
        return (self.curr_x, self.curr_y)
