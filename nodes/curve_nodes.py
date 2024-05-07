import torch
from torchvision import transforms
import json
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from ..utility.utility import pil2tensor
import folder_paths

def plot_coordinates_to_tensor(coordinates, height, width, bbox_height, bbox_width, size_multiplier, prompt):
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
        text_color = '#999999'
        bg_color = '#353535'
        matplotlib.pyplot.rcParams['text.color'] = text_color
        fig, ax = matplotlib.pyplot.subplots(figsize=(width/100, height/100), dpi=100)
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)
        ax.grid(color=text_color, linestyle='-', linewidth=0.5)
        ax.set_xlabel('x', color=text_color)
        ax.set_ylabel('y', color=text_color)
        for text in ax.get_xticklabels() + ax.get_yticklabels():
            text.set_color(text_color)
        ax.set_title('position for: ' + prompt)
        ax.set_xlabel('X Coordinate')
        ax.set_ylabel('Y Coordinate')
        #ax.legend().remove()
        ax.set_xlim(0, width) # Set the x-axis to match the input latent width
        ax.set_ylim(height, 0) # Set the y-axis to match the input latent height, with (0,0) at top-left
        # Adjust the margins of the subplot
        matplotlib.pyplot.subplots_adjust(left=0.08, right=0.95, bottom=0.05, top=0.95, wspace=0.2, hspace=0.2)

        cmap = matplotlib.pyplot.get_cmap('rainbow')
        image_batch = []
        canvas = FigureCanvas(fig)
        width, height = fig.get_size_inches() * fig.get_dpi()
        # Draw a box at each coordinate
        for i, ((x, y), size) in enumerate(zip(coordinates, size_multiplier)):
            color_index = i / (len(coordinates) - 1)
            color = cmap(color_index)
            draw_height = bbox_height * size
            draw_width = bbox_width * size
            rect = matplotlib.patches.Rectangle((x - draw_width/2, y - draw_height/2), draw_width, draw_height,
                                            linewidth=1, edgecolor=color, facecolor='none', alpha=0.5)
            ax.add_patch(rect)

            # Check if there is a next coordinate to draw an arrow to
            if i < len(coordinates) - 1:
                x1, y1 = coordinates[i]
                x2, y2 = coordinates[i + 1]
                ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                            arrowprops=dict(arrowstyle="->",
                                            linestyle="-",
                                            lw=1,
                                            color=color,
                                            mutation_scale=20))
            canvas.draw()
            image_np = np.frombuffer(canvas.tostring_rgb(), dtype='uint8').reshape(int(height), int(width), 3).copy()
            image_tensor = torch.from_numpy(image_np).float() / 255.0
            image_tensor = image_tensor.unsqueeze(0)
            image_batch.append(image_tensor)
            
        matplotlib.pyplot.close(fig)
        image_batch_tensor = torch.cat(image_batch, dim=0)

        return image_batch_tensor

class PlotCoordinates:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
                              "coordinates": ("STRING", {"forceInput": True}),
                              "text": ("STRING", {"default": 'title', "multiline": False}),
                              "width": ("INT", {"default": 512, "min": 8, "max": 4096, "step": 8}),
                              "height": ("INT", {"default": 512, "min": 8, "max": 4096, "step": 8}),
                              "bbox_width": ("INT", {"default": 128, "min": 8, "max": 4096, "step": 8}),
                              "bbox_height": ("INT", {"default": 128, "min": 8, "max": 4096, "step": 8}),
                            },
                "optional": {"size_multiplier": ("FLOAT", {"default": [1.0], "forceInput": True})},
                }
    RETURN_TYPES = ("IMAGE", "INT", "INT", "INT", "INT",)
    RETURN_NAMES = ("images", "width", "height", "bbox_width", "bbox_height",)
    FUNCTION = "append"
    CATEGORY = "KJNodes/experimental"
    DESCRIPTION = """
Plots coordinates to sequence of images using Matplotlib.  

"""

    def append(self, coordinates, text, width, height, bbox_width, bbox_height, size_multiplier=[1.0]):
        coordinates = json.loads(coordinates.replace("'", '"'))
        coordinates = [(coord['x'], coord['y']) for coord in coordinates]
        batch_size = len(coordinates)    
        if len(size_multiplier) != batch_size:
            size_multiplier = size_multiplier * (batch_size // len(size_multiplier)) + size_multiplier[:batch_size % len(size_multiplier)]

        plot_image_tensor = plot_coordinates_to_tensor(coordinates, height, width, bbox_height, bbox_width, size_multiplier, text)
        
        return (plot_image_tensor, width, height, bbox_width, bbox_height)
    
class SplineEditor:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "points_store": ("STRING", {"multiline": False}),
                "coordinates": ("STRING", {"multiline": False}),
                "mask_width": ("INT", {"default": 512, "min": 8, "max": 4096, "step": 8}),
                "mask_height": ("INT", {"default": 512, "min": 8, "max": 4096, "step": 8}),
                "points_to_sample": ("INT", {"default": 16, "min": 2, "max": 1000, "step": 1}),
                "sampling_method": (
                [   
                    'path',
                    'time',
                ],
                {
                    "default": 'time'
                }),
                "interpolation": (
                [   
                    'cardinal',
                    'monotone',
                    'basis',
                    'linear',
                    'step-before',
                    'step-after',
                    'polar',
                    'polar-reverse',
                ],
                {
                "default": 'cardinal'
                    }),
                "tension": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                "repeat_output": ("INT", {"default": 1, "min": 1, "max": 4096, "step": 1}),
                "float_output_type": (
                [   
                    'list',
                    'pandas series',
                    'tensor',
                ],
                {
                    "default": 'list'
                }),
            },
            "optional": {
                "min_value": ("FLOAT", {"default": 0.0, "min": -10000.0, "max": 10000.0, "step": 0.01}),
                "max_value": ("FLOAT", {"default": 1.0, "min": -10000.0, "max": 10000.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("MASK", "STRING", "FLOAT", "INT")
    RETURN_NAMES = ("mask", "coord_str", "float", "count")
    FUNCTION = "splinedata"
    CATEGORY = "KJNodes/weights"
    DESCRIPTION = """
# WORK IN PROGRESS  
Do not count on this as part of your workflow yet,  
probably contains lots of bugs and stability is not  
guaranteed!!  
  
## Graphical editor to create values for various   
## schedules and/or mask batches.  

**Shift + click** to add control point at end.
**Ctrl + click** to add control point (subdivide) between two points.  
**Right click on a point** to delete it.    
Note that you can't delete from start/end.  
  
Right click on canvas for context menu:  
These are purely visual options, doesn't affect the output:  
 - Toggle handles visibility
 - Display sample points: display the points to be returned.  

**points_to_sample** value sets the number of samples  
returned from the **drawn spline itself**, this is independent from the  
actual control points, so the interpolation type matters.  
sampling_method: 
 - time: samples along the time axis, used for schedules  
 - path: samples along the path itself, useful for coordinates  

output types:
 - mask batch  
        example compatible nodes: anything that takes masks  
 - list of floats
        example compatible nodes: IPAdapter weights  
 - pandas series
        example compatible nodes: anything that takes Fizz'  
        nodes Batch Value Schedule  
 - torch tensor  
        example compatible nodes: unknown
"""

    def splinedata(self, mask_width, mask_height, coordinates, float_output_type, interpolation, 
                   points_to_sample, sampling_method, points_store, tension, repeat_output, min_value=0.0, max_value=1.0):
        
        coordinates = json.loads(coordinates)
        for coord in coordinates:
            coord['x'] = int(round(coord['x']))
            coord['y'] = int(round(coord['y']))
            
        normalized_y_values = [
            (1.0 - (point['y'] / mask_height) - 0.0) * (max_value - min_value) + min_value
            for point in coordinates
        ]
        if float_output_type == 'list':
            out_floats = normalized_y_values * repeat_output
        elif float_output_type == 'pandas series':
            try:
                import pandas as pd
            except:
                raise Exception("MaskOrImageToWeight: pandas is not installed. Please install pandas to use this output_type")
            out_floats = pd.Series(normalized_y_values * repeat_output),
        elif float_output_type == 'tensor':
            out_floats = torch.tensor(normalized_y_values * repeat_output, dtype=torch.float32)
        # Create a color map for grayscale intensities
        color_map = lambda y: torch.full((mask_height, mask_width, 3), y, dtype=torch.float32)

        # Create image tensors for each normalized y value
        mask_tensors = [color_map(y) for y in normalized_y_values]
        masks_out = torch.stack(mask_tensors)
        masks_out = masks_out.repeat(repeat_output, 1, 1, 1)
        masks_out = masks_out.mean(dim=-1)
        return (masks_out, str(coordinates), out_floats, len(out_floats))

class CreateShapeMaskOnPath:
    
    RETURN_TYPES = ("MASK", "MASK",)
    RETURN_NAMES = ("mask", "mask_inverted",)
    FUNCTION = "createshapemask"
    CATEGORY = "KJNodes/masking/generate"
    DESCRIPTION = """
Creates a mask or batch of masks with the specified shape.  
Locations are center locations.  
"""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "shape": (
            [   'circle',
                'square',
                'triangle',
            ],
            {
            "default": 'circle'
             }),
                "coordinates": ("STRING", {"forceInput": True}),
                "frame_width": ("INT", {"default": 512,"min": 16, "max": 4096, "step": 1}),
                "frame_height": ("INT", {"default": 512,"min": 16, "max": 4096, "step": 1}),
                "shape_width": ("INT", {"default": 128,"min": 8, "max": 4096, "step": 1}),
                "shape_height": ("INT", {"default": 128,"min": 8, "max": 4096, "step": 1}),
        },
        "optional": {
            "size_multiplier": ("FLOAT", {"default": [1.0], "forceInput": True}),
        }
    } 

    def createshapemask(self, coordinates, frame_width, frame_height, shape_width, shape_height, shape, size_multiplier=[1.0]):
        # Define the number of images in the batch
        coordinates = coordinates.replace("'", '"')
        coordinates = json.loads(coordinates)

        batch_size = len(coordinates)
        out = []
        color = "white"
        if len(size_multiplier) != batch_size:
            size_multiplier = size_multiplier * (batch_size // len(size_multiplier)) + size_multiplier[:batch_size % len(size_multiplier)]
        for i, coord in enumerate(coordinates):
            image = Image.new("RGB", (frame_width, frame_height), "black")
            draw = ImageDraw.Draw(image)

            # Calculate the size for this frame and ensure it's not less than 0
            current_width = max(0, shape_width + i * size_multiplier[i])
            current_height = max(0, shape_height + i * size_multiplier[i])

            location_x = coord['x']
            location_y = coord['y']

            if shape == 'circle' or shape == 'square':
                # Define the bounding box for the shape
                left_up_point = (location_x - current_width // 2, location_y - current_height // 2)
                right_down_point = (location_x + current_width // 2, location_y + current_height // 2)
                two_points = [left_up_point, right_down_point]

                if shape == 'circle':
                    draw.ellipse(two_points, fill=color)
                elif shape == 'square':
                    draw.rectangle(two_points, fill=color)
                    
            elif shape == 'triangle':
                # Define the points for the triangle
                left_up_point = (location_x - current_width // 2, location_y + current_height // 2) # bottom left
                right_down_point = (location_x + current_width // 2, location_y + current_height // 2) # bottom right
                top_point = (location_x, location_y - current_height // 2) # top point
                draw.polygon([top_point, left_up_point, right_down_point], fill=color)

            image = pil2tensor(image)
            mask = image[:, :, :, 0]
            out.append(mask)
        outstack = torch.cat(out, dim=0)
        return (outstack, 1.0 - outstack,)
    
class CreateTextOnPath:
    
    RETURN_TYPES = ("IMAGE", "MASK", "MASK",)
    RETURN_NAMES = ("image", "mask", "mask_inverted",)
    FUNCTION = "createtextmask"
    CATEGORY = "KJNodes/masking/generate"
    DESCRIPTION = """
Creates a mask or batch of masks with the specified text.  
Locations are center locations.  
"""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "coordinates": ("STRING", {"forceInput": True}),
                "text": ("STRING", {"default": 'text', "multiline": True}),
                "frame_width": ("INT", {"default": 512,"min": 16, "max": 4096, "step": 1}),
                "frame_height": ("INT", {"default": 512,"min": 16, "max": 4096, "step": 1}),
                "font": (folder_paths.get_filename_list("kjnodes_fonts"), ),
                "font_size": ("INT", {"default": 42}),
                 "alignment": (
                [   'left',
                    'center',
                    'right'
                ],
                {"default": 'center'}
                ),
                "text_color": ("STRING", {"default": 'white'}),
        },
        "optional": {
            "size_multiplier": ("FLOAT", {"default": [1.0], "forceInput": True}),
        }
    } 

    def createtextmask(self, coordinates, frame_width, frame_height, font, font_size, text, text_color, alignment, size_multiplier=[1.0]):
        coordinates = coordinates.replace("'", '"')
        coordinates = json.loads(coordinates)

        batch_size = len(coordinates)
        mask_list = []
        image_list = []
        color = text_color
        font_path = folder_paths.get_full_path("kjnodes_fonts", font)

        if len(size_multiplier) != batch_size:
            size_multiplier = size_multiplier * (batch_size // len(size_multiplier)) + size_multiplier[:batch_size % len(size_multiplier)]
        
        for i, coord in enumerate(coordinates):
            image = Image.new("RGB", (frame_width, frame_height), "black")
            draw = ImageDraw.Draw(image)
            lines = text.split('\n')  # Split the text into lines
            # Apply the size multiplier to the font size for this iteration
            current_font_size = int(font_size * size_multiplier[i])
            current_font = ImageFont.truetype(font_path, current_font_size)
            line_heights = [current_font.getbbox(line)[3] for line in lines]  # List of line heights
            total_text_height = sum(line_heights)  # Total height of text block

            # Calculate the starting Y position to center the block of text
            start_y = coord['y'] - total_text_height // 2
            for j, line in enumerate(lines):
                text_width, text_height = current_font.getbbox(line)[2], line_heights[j]
                if alignment == 'left':
                    location_x = coord['x']
                elif alignment == 'center':
                    location_x = int(coord['x'] - text_width // 2)
                elif alignment == 'right':
                    location_x = int(coord['x'] - text_width)
                
                location_y = int(start_y + sum(line_heights[:j]))
                text_position = (location_x, location_y)
                # Draw the text
                try:
                    draw.text(text_position, line, fill=color, font=current_font, features=['-liga'])
                except:
                    draw.text(text_position, line, fill=color, font=current_font)
            
            image = pil2tensor(image)
            non_black_pixels = (image > 0).any(dim=-1)
            mask = non_black_pixels.to(image.dtype)
            mask_list.append(mask)
            image_list.append(image)

        out_images = torch.cat(image_list, dim=0).cpu().float()
        out_masks = torch.cat(mask_list, dim=0)
        return (out_images, out_masks, 1.0 - out_masks,)
    
class MaskOrImageToWeight:

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "output_type": (
                [   
                    'list',
                    'pandas series',
                    'tensor',
                    'string'
                ],
                {
                "default": 'list'
                    }),
             },
            "optional": {
                "images": ("IMAGE",),
                "masks": ("MASK",),                
            },

        }
    RETURN_TYPES = ("FLOAT", "STRING",)
    FUNCTION = "execute"
    CATEGORY = "KJNodes/weights"
    DESCRIPTION = """
Gets the mean values from mask or image batch  
and returns that as the selected output type.   
"""

    def execute(self, output_type, images=None, masks=None):
        mean_values = []
        if masks is not None and images is None:
            for mask in masks:
                mean_values.append(mask.mean().item())
        elif masks is None and images is not None:
            for image in images:
                mean_values.append(image.mean().item())
        elif masks is not None and images is not None:
            raise Exception("MaskOrImageToWeight: Use either mask or image input only.")
                  
        # Convert mean_values to the specified output_type
        if output_type == 'list':
            out = mean_values,
        elif output_type == 'pandas series':
            try:
                import pandas as pd
            except:
                raise Exception("MaskOrImageToWeight: pandas is not installed. Please install pandas to use this output_type")
            out = pd.Series(mean_values),
        elif output_type == 'tensor':
            out = torch.tensor(mean_values, dtype=torch.float32),
        return (out, [str(value) for value in mean_values],)
    
class WeightScheduleConvert:

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "input_values": ("FLOAT", {"default": 0.0, "forceInput": True}),
                "output_type": (
                [   
                    'match_input',
                    'list',
                    'pandas series',
                    'tensor',
                ],
                {
                "default": 'list'
                    }),
                "invert": ("BOOLEAN", {"default": False}),
                "repeat": ("INT", {"default": 1,"min": 1, "max": 255, "step": 1}),
             },
             "optional": {
                "remap_to_frames": ("INT", {"default": 0}),
                "interpolation_curve": ("FLOAT", {"forceInput": True}),
                "remap_values": ("BOOLEAN", {"default": False}),
                "remap_min": ("FLOAT", {"default": 0.0, "min": -100000, "max": 100000.0, "step": 0.01}),
                "remap_max": ("FLOAT", {"default": 1.0, "min": -100000, "max": 100000.0, "step": 0.01}),
             },
             
        }
    RETURN_TYPES = ("FLOAT", "STRING", "INT",)
    FUNCTION = "execute"
    CATEGORY = "KJNodes/weights"
    DESCRIPTION = """
Converts different value lists/series to another type.  
"""

    def detect_input_type(self, input_values):
        import pandas as pd
        if isinstance(input_values, list):
            return 'list'
        elif isinstance(input_values, pd.Series):
            return 'pandas series'
        elif isinstance(input_values, torch.Tensor):
            return 'tensor'
        else:
            raise ValueError("Unsupported input type")

    def execute(self, input_values, output_type, invert, repeat, remap_to_frames=0, interpolation_curve=None, remap_min=0.0, remap_max=1.0, remap_values=False):
        import pandas as pd
        input_type = self.detect_input_type(input_values)

        if input_type == 'pandas series':
            float_values = input_values.tolist()
        elif input_type == 'tensor':
            float_values = input_values
        else:
            float_values = input_values

        if invert:
            float_values = [1 - value for value in float_values]

        if interpolation_curve is not None:
            interpolated_pattern = []
            orig_float_values = float_values
            for value in interpolation_curve:
                min_val = min(orig_float_values)
                max_val = max(orig_float_values)
                # Normalize the values to [0, 1]
                normalized_values = [(value - min_val) / (max_val - min_val) for value in orig_float_values]
                # Interpolate the normalized values to the new frame count
                remapped_float_values = np.interp(np.linspace(0, 1, int(remap_to_frames * value)), np.linspace(0, 1, len(normalized_values)), normalized_values).tolist()
                interpolated_pattern.extend(remapped_float_values)
            float_values = interpolated_pattern
        else:
            # Remap float_values to match target_frame_amount
            if remap_to_frames > 0 and remap_to_frames != len(float_values):
                min_val = min(float_values)
                max_val = max(float_values)
                # Normalize the values to [0, 1]
                normalized_values = [(value - min_val) / (max_val - min_val) for value in float_values]
                # Interpolate the normalized values to the new frame count
                float_values = np.interp(np.linspace(0, 1, remap_to_frames), np.linspace(0, 1, len(normalized_values)), normalized_values).tolist()
       
            float_values = float_values * repeat
            if remap_values:
                float_values = self.remap_values(float_values, remap_min, remap_max)

        if output_type == 'list':
            out = float_values,
        elif output_type == 'pandas series':
            out = pd.Series(float_values),
        elif output_type == 'tensor':
            if input_type == 'pandas series':
                out = torch.tensor(float_values.values, dtype=torch.float32),
            else:   
                out = torch.tensor(float_values, dtype=torch.float32),
        elif output_type == 'match_input':
            out = float_values,
        return (out, [str(value) for value in float_values], [int(value) for value in float_values])
    
    def remap_values(self, values, target_min, target_max):
        # Determine the current range
        current_min = min(values)
        current_max = max(values)
        current_range = current_max - current_min
        
        # Determine the target range
        target_range = target_max - target_min
        
        # Perform the linear interpolation for each value
        remapped_values = [(value - current_min) / current_range * target_range + target_min for value in values]
        
        return remapped_values
        

class FloatToMask:

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "input_values": ("FLOAT", {"forceInput": True, "default": 0}),
                "width": ("INT", {"default": 100, "min": 1}),
                "height": ("INT", {"default": 100, "min": 1}),
            },
        }
    RETURN_TYPES = ("MASK",)
    FUNCTION = "execute"
    CATEGORY = "KJNodes/masking/generate"
    DESCRIPTION = """
Generates a batch of masks based on the input float values.
The batch size is determined by the length of the input float values.
Each mask is generated with the specified width and height.
"""

    def execute(self, input_values, width, height):
        import pandas as pd
        # Ensure input_values is a list
        if isinstance(input_values, (float, int)):
            input_values = [input_values]
        elif isinstance(input_values, pd.Series):
            input_values = input_values.tolist()
        elif isinstance(input_values, list) and all(isinstance(item, list) for item in input_values):
            input_values = [item for sublist in input_values for item in sublist]

        # Generate a batch of masks based on the input_values
        masks = []
        for value in input_values:
            # Assuming value is a float between 0 and 1 representing the mask's intensity
            mask = torch.ones((height, width), dtype=torch.float32) * value
            masks.append(mask)
        masks_out = torch.stack(masks, dim=0)
    
        return(masks_out,)
class WeightScheduleExtend:

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "input_values_1": ("FLOAT", {"default": 0.0, "forceInput": True}),
                "input_values_2": ("FLOAT", {"default": 0.0, "forceInput": True}),
                "output_type": (
                [   
                    'match_input',
                    'list',
                    'pandas series',
                    'tensor',
                ],
                {
                "default": 'match_input'
                    }),
             },
             
        }
    RETURN_TYPES = ("FLOAT",)
    FUNCTION = "execute"
    CATEGORY = "KJNodes/weights"
    DESCRIPTION = """
Extends, and converts if needed, different value lists/series  
"""

    def detect_input_type(self, input_values):
        import pandas as pd
        if isinstance(input_values, list):
            return 'list'
        elif isinstance(input_values, pd.Series):
            return 'pandas series'
        elif isinstance(input_values, torch.Tensor):
            return 'tensor'
        else:
            raise ValueError("Unsupported input type")

    def execute(self, input_values_1, input_values_2, output_type):
        import pandas as pd
        input_type_1 = self.detect_input_type(input_values_1)
        input_type_2 = self.detect_input_type(input_values_2)
        # Convert input_values_2 to the same format as input_values_1 if they do not match
        if not input_type_1 == input_type_2:
            print("Converting input_values_2 to the same format as input_values_1")
            if input_type_1 == 'pandas series':
                # Convert input_values_2 to a pandas Series
                float_values_2 = pd.Series(input_values_2)
            elif input_type_1 == 'tensor':
                # Convert input_values_2 to a tensor
                float_values_2 = torch.tensor(input_values_2, dtype=torch.float32)
        else:
            print("Input types match, no conversion needed")
            # If the types match, no conversion is needed
            float_values_2 = input_values_2
     
        float_values = input_values_1 + float_values_2
 
        if output_type == 'list':
            return float_values,
        elif output_type == 'pandas series':
            return pd.Series(float_values),
        elif output_type == 'tensor':
            if input_type_1 == 'pandas series':
                return torch.tensor(float_values.values, dtype=torch.float32),
            else:
                return torch.tensor(float_values, dtype=torch.float32),
        elif output_type == 'match_input':
            return float_values,
        else:
            raise ValueError(f"Unsupported output_type: {output_type}")
        
class FloatToSigmas:
    @classmethod
    def INPUT_TYPES(s):
        return {"required":
                    {
                     "float_list": ("FLOAT", {"default": 0.0, "forceInput": True}),
                     }
                }
    RETURN_TYPES = ("SIGMAS",)
    RETURN_NAMES = ("SIGMAS",)
    CATEGORY = "KJNodes/noise"
    FUNCTION = "customsigmas"
    DESCRIPTION = """
Creates a sigmas tensor from list of float values.  

"""
    def customsigmas(self, float_list):
        return torch.tensor(float_list, dtype=torch.float32),

class GLIGENTextBoxApplyBatchCoords:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"conditioning_to": ("CONDITIONING", ),
                              "latents": ("LATENT", ),
                              "clip": ("CLIP", ),
                              "gligen_textbox_model": ("GLIGEN", ),
                              "coordinates": ("STRING", {"forceInput": True}),
                              "text": ("STRING", {"multiline": True}),
                              "width": ("INT", {"default": 128, "min": 8, "max": 4096, "step": 8}),
                              "height": ("INT", {"default": 128, "min": 8, "max": 4096, "step": 8}),
                            },
                "optional": {"size_multiplier": ("FLOAT", {"default": [1.0], "forceInput": True})},
                }
    RETURN_TYPES = ("CONDITIONING", "IMAGE", )
    RETURN_NAMES = ("conditioning", "coord_preview", )
    FUNCTION = "append"
    CATEGORY = "KJNodes/experimental"
    DESCRIPTION = """
This node allows scheduling GLIGEN text box positions in a batch,  
to be used with AnimateDiff-Evolved. Intended to pair with the  
Spline Editor -node.  

GLIGEN model can be downloaded through the Manage's "Install Models" menu.  
Or directly from here:  
https://huggingface.co/comfyanonymous/GLIGEN_pruned_safetensors/tree/main  
  
Inputs:  
- **latents** input is used to calculate batch size  
- **clip** is your standard text encoder, use same as for the main prompt  
- **gligen_textbox_model** connects to GLIGEN Loader  
- **coordinates** takes a json string of points, directly compatible  
with the spline editor node.
- **text** is the part of the prompt to set position for  
- **width** and **height** are the size of the GLIGEN bounding box  
  
Outputs:
- **conditioning** goes between to clip text encode and the sampler  
- **coord_preview** is an optional preview of the coordinates and  
bounding boxes.

"""

    def append(self, latents, coordinates, conditioning_to, clip, gligen_textbox_model, text, width, height, size_multiplier=[1.0]):
        coordinates = json.loads(coordinates.replace("'", '"'))
        coordinates = [(coord['x'], coord['y']) for coord in coordinates]

        batch_size = sum(tensor.size(0) for tensor in latents.values())
        if len(coordinates) != batch_size:
            print("GLIGENTextBoxApplyBatchCoords WARNING: The number of coordinates does not match the number of latents")

        c = []
        _, cond_pooled = clip.encode_from_tokens(clip.tokenize(text), return_pooled=True)

        for t in conditioning_to:
            n = [t[0], t[1].copy()]
            
            position_params_batch = [[] for _ in range(batch_size)]  # Initialize a list of empty lists for each batch item
            if len(size_multiplier) != batch_size:
                size_multiplier = size_multiplier * (batch_size // len(size_multiplier)) + size_multiplier[:batch_size % len(size_multiplier)]

            for i in range(batch_size):
                x_position, y_position = coordinates[i]
                position_param = (cond_pooled, int((height // 8) * size_multiplier[i]), int((width // 8) * size_multiplier[i]), (y_position - height // 2) // 8, (x_position - width // 2) // 8)
                position_params_batch[i].append(position_param)  # Append position_param to the correct sublist

            prev = []
            if "gligen" in n[1]:
                prev = n[1]['gligen'][2]
            else:
                prev = [[] for _ in range(batch_size)]
            # Concatenate prev and position_params_batch, ensuring both are lists of lists
            # and each sublist corresponds to a batch item
            combined_position_params = [prev_item + batch_item for prev_item, batch_item in zip(prev, position_params_batch)]
            n[1]['gligen'] = ("position_batched", gligen_textbox_model, combined_position_params)
            c.append(n)

        image_height = latents['samples'].shape[-2] * 8
        image_width = latents['samples'].shape[-1] * 8
        plot_image_tensor = plot_coordinates_to_tensor(coordinates, image_height, image_width, height, width, size_multiplier, text)
        
        return (c, plot_image_tensor,)
    
class CreateInstanceDiffusionTracking:
    
    RETURN_TYPES = ("TRACKING", "STRING", "INT", "INT", "INT", "INT",)
    RETURN_NAMES = ("tracking", "prompt", "width", "height", "bbox_width", "bbox_height",)
    FUNCTION = "tracking"
    CATEGORY = "KJNodes/InstanceDiffusion"
    DESCRIPTION = """
Creates tracking data to be used with InstanceDiffusion:  
https://github.com/logtd/ComfyUI-InstanceDiffusion  
  
InstanceDiffusion prompt format:  
"class_id.class_name": "prompt",  
for example:  
"1.head": "((head))",  
"""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "coordinates": ("STRING", {"forceInput": True}),
                "width": ("INT", {"default": 512,"min": 16, "max": 4096, "step": 1}),
                "height": ("INT", {"default": 512,"min": 16, "max": 4096, "step": 1}),
                "bbox_width": ("INT", {"default": 512,"min": 16, "max": 4096, "step": 1}),
                "bbox_height": ("INT", {"default": 512,"min": 16, "max": 4096, "step": 1}),
                "class_name": ("STRING", {"default": "class_name"}),
                "class_id": ("INT", {"default": 0,"min": 0, "max": 255, "step": 1}),
                "prompt": ("STRING", {"default": "prompt", "multiline": True}),
        },
        "optional": {
            "size_multiplier": ("FLOAT", {"default": [1.0], "forceInput": True}),
            "fit_in_frame": ("BOOLEAN", {"default": True}),
        }
    } 

    def tracking(self, coordinates, class_name, class_id, width, height, bbox_width, bbox_height, prompt, size_multiplier=[1.0], fit_in_frame=True):
        # Define the number of images in the batch
        coordinates = coordinates.replace("'", '"')
        coordinates = json.loads(coordinates)

        tracked = {}
        tracked[class_name] = {}
        batch_size = len(coordinates)
        # Initialize a list to hold the coordinates for the current ID
        id_coordinates = []
        if len(size_multiplier) != batch_size:
                size_multiplier = size_multiplier * (batch_size // len(size_multiplier)) + size_multiplier[:batch_size % len(size_multiplier)]
        for i, coord in enumerate(coordinates):
            x = coord['x']
            y = coord['y']
            adjusted_bbox_width = bbox_width * size_multiplier[i]
            adjusted_bbox_height = bbox_height * size_multiplier[i]
            # Calculate the top left and bottom right coordinates
            top_left_x = x - adjusted_bbox_width // 2
            top_left_y = y - adjusted_bbox_height // 2
            bottom_right_x = x + adjusted_bbox_width // 2
            bottom_right_y = y + adjusted_bbox_height // 2

            if fit_in_frame:
                # Clip the coordinates to the frame boundaries
                top_left_x = max(0, top_left_x)
                top_left_y = max(0, top_left_y)
                bottom_right_x = min(width, bottom_right_x)
                bottom_right_y = min(height, bottom_right_y)
                # Ensure width and height are positive
                adjusted_bbox_width = max(1, bottom_right_x - top_left_x)
                adjusted_bbox_height = max(1, bottom_right_y - top_left_y)

                # Update the coordinates with the new width and height
                bottom_right_x = top_left_x + adjusted_bbox_width
                bottom_right_y = top_left_y + adjusted_bbox_height

            # Append the top left and bottom right coordinates to the list for the current ID
            id_coordinates.append([top_left_x, top_left_y, bottom_right_x, bottom_right_y, width, height])
        
        class_id = int(class_id)
        # Assign the list of coordinates to the specified ID within the class_id dictionary
        tracked[class_name][class_id] = id_coordinates

        prompt_string = ""
        for class_name, class_data in tracked.items():
            for class_id in class_data.keys():
                class_id_str = str(class_id)
                # Use the incoming prompt for each class name and ID
                prompt_string += f'"{class_id_str}.{class_name}": "({prompt})",\n'

        # Remove the last comma and newline
        prompt_string = prompt_string.rstrip(",\n")

        return (tracked, prompt_string, width, height, bbox_width, bbox_height)

class AppendInstanceDiffusionTracking:
    
    RETURN_TYPES = ("TRACKING", "STRING",)
    RETURN_NAMES = ("tracking", "prompt",)
    FUNCTION = "append"
    CATEGORY = "KJNodes/InstanceDiffusion"
    DESCRIPTION = """
Appends tracking data to be used with InstanceDiffusion:  
https://github.com/logtd/ComfyUI-InstanceDiffusion  

"""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "tracking_1": ("TRACKING", {"forceInput": True}),
                "tracking_2": ("TRACKING", {"forceInput": True}),
        },
        "optional": {
            "prompt_1": ("STRING", {"default": "", "forceInput": True}),
            "prompt_2": ("STRING", {"default": "", "forceInput": True}),
        }
    } 

    def append(self, tracking_1, tracking_2, prompt_1="", prompt_2=""):
        tracking_copy = tracking_1.copy()
        # Check for existing class names and class IDs, and raise an error if they exist
        for class_name, class_data in tracking_2.items():
            if class_name not in tracking_copy:
                tracking_copy[class_name] = class_data
            else:
                # If the class name exists, merge the class data from tracking_2 into tracking_copy
                # This will add new class IDs under the same class name without raising an error
                tracking_copy[class_name].update(class_data)
        prompt_string = prompt_1 + "," + prompt_2
        return (tracking_copy, prompt_string)
        
class InterpolateCoords:
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("coordinates",)
    FUNCTION = "interpolate"
    CATEGORY = "KJNodes/experimental"
    DESCRIPTION = """
Interpolates coordinates based on a curve.   
"""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "coordinates": ("STRING", {"forceInput": True}),
                "interpolation_curve": ("FLOAT", {"forceInput": True}),
                
        },
    } 

    def interpolate(self, coordinates, interpolation_curve):
        # Parse the JSON string to get the list of coordinates
        coordinates = json.loads(coordinates.replace("'", '"'))

        # Convert the list of dictionaries to a list of (x, y) tuples for easier processing
        coordinates = [(coord['x'], coord['y']) for coord in coordinates]

        # Calculate the total length of the original path
        path_length = sum(np.linalg.norm(np.array(coordinates[i]) - np.array(coordinates[i-1])) 
                        for i in range(1, len(coordinates)))

        # Initialize variables for interpolation
        interpolated_coords = []
        current_length = 0
        current_index = 0

        # Iterate over the normalized curve
        for normalized_length in interpolation_curve:
            target_length = normalized_length * path_length # Convert to the original scale
            while current_index < len(coordinates) - 1:
                segment_start, segment_end = np.array(coordinates[current_index]), np.array(coordinates[current_index + 1])
                segment_length = np.linalg.norm(segment_end - segment_start)
                if current_length + segment_length >= target_length:
                    break
                current_length += segment_length
                current_index += 1

            # Interpolate between the last two points
            if current_index < len(coordinates) - 1:
                p1, p2 = np.array(coordinates[current_index]), np.array(coordinates[current_index + 1])
                segment_length = np.linalg.norm(p2 - p1)
                if segment_length > 0:
                    t = (target_length - current_length) / segment_length
                    interpolated_point = p1 + t * (p2 - p1)
                    interpolated_coords.append(interpolated_point.tolist())
                else:
                    interpolated_coords.append(p1.tolist())
            else:
                # If the target_length is at or beyond the end of the path, add the last coordinate
                interpolated_coords.append(coordinates[-1])

        # Convert back to string format if necessary
        interpolated_coords_str = "[" + ", ".join([f"{{'x': {round(coord[0])}, 'y': {round(coord[1])}}}" for coord in interpolated_coords]) + "]"
        print(interpolated_coords_str)

        return (interpolated_coords_str,)
    
class DrawInstanceDiffusionTracking:
    
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image", )
    FUNCTION = "draw"
    CATEGORY = "KJNodes/InstanceDiffusion"
    DESCRIPTION = """
Draws the tracking data from  
CreateInstanceDiffusionTracking -node.

"""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE", ),
                "tracking": ("TRACKING", {"forceInput": True}),
                "box_line_width": ("INT", {"default": 2, "min": 1, "max": 10, "step": 1}),
                "draw_text": ("BOOLEAN", {"default": True}),
                "font": (folder_paths.get_filename_list("kjnodes_fonts"), ),
                "font_size": ("INT", {"default": 20}),
        },
    } 

    def draw(self, image, tracking, box_line_width, draw_text, font, font_size):
        import matplotlib.cm as cm

        modified_images = []
        
        colormap = cm.get_cmap('rainbow', len(tracking))
        if draw_text:
            font_path = folder_paths.get_full_path("kjnodes_fonts", font)
            font = ImageFont.truetype(font_path, font_size)

        # Iterate over each image in the batch
        for i in range(image.shape[0]):
            # Extract the current image and convert it to a PIL image
            current_image = image[i, :, :, :].permute(2, 0, 1)
            pil_image = transforms.ToPILImage()(current_image)
            
            draw = ImageDraw.Draw(pil_image)
            
            # Iterate over the bounding boxes for the current image
            for j, (class_name, class_data) in enumerate(tracking.items()):
                for class_id, bbox_list in class_data.items():
                    # Check if the current index is within the bounds of the bbox_list
                    if i < len(bbox_list):
                        bbox = bbox_list[i]
                        # Ensure bbox is a list or tuple before unpacking
                        if isinstance(bbox, (list, tuple)):
                            x1, y1, x2, y2, _, _ = bbox
                            # Convert coordinates to integers
                            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                            # Generate a color from the rainbow colormap
                            color = tuple(int(255 * x) for x in colormap(j / len(tracking)))[:3]
                            # Draw the bounding box on the image with the generated color
                            draw.rectangle([x1, y1, x2, y2], outline=color, width=box_line_width)
                            if draw_text:
                                # Draw the class name and ID as text above the box with the generated color
                                text = f"{class_id}.{class_name}"
                                # Calculate the width and height of the text
                                _, _, text_width, text_height = draw.textbbox((0, 0), text=text, font=font)
                                # Position the text above the top-left corner of the box
                                text_position = (x1, y1 - text_height)
                                draw.text(text_position, text, fill=color, font=font)
                        else:
                            print(f"Unexpected data type for bbox: {type(bbox)}")
            
            # Convert the drawn image back to a torch tensor and adjust back to (H, W, C)
            modified_image_tensor = transforms.ToTensor()(pil_image).permute(1, 2, 0)
            modified_images.append(modified_image_tensor)
        
        # Stack the modified images back into a batch
        image_tensor_batch = torch.stack(modified_images).cpu().float()
        
        return image_tensor_batch,