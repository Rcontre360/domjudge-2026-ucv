import os
import shutil
import zipfile
from pypdf import PdfReader, PdfWriter

problems = [
    {
        'id': 'a',
        'name': 'Gestión de Recursos de la Flota',
        'pages': [3],
        'samples': [
            ("2 10 7\n2 3 7 2\n3 2 6 3\n", "14\n"),
            ("3 15 10\n4 3 8 2\n5 4 10 1\n2 1 3 5\n", "27\n")
        ]
    },
    {
        'id': 'b',
        'name': 'Código de Transmisión',
        'pages': [4],
        'samples': [
            ("3 3\nllorar\ncomida\ngato\n4286\n76669\n266432\n", "1 gato\n0\n1 comida\n"),
            ("4 2\ncala\nbaja\ncaja\nzanja\n2242\n92652\n", "3 baja caja cala\n1 zanja\n")
        ]
    },
    {
        'id': 'c',
        'name': 'Rascacielos en Coruscant',
        'pages': [5],
        'samples': [
            ("4\n3 2 5 2\n", "8\n"),
            ("6\n3 2 1 5 6 4\n", "12\n")
        ]
    },
    {
        'id': 'd',
        'name': 'Ruta Hiperespacial',
        'pages': [6],
        'samples': [
            ("5 4\ncube cone cine cure core\ncine cube\n", "cine cone core cure cube\n"),
            ("4 5\nparma calma perma palma\ncalma perma\n", "calma palma parma perma\n"),
            ("5 3\ntoo top ton cap tap\ntop cap\n", "top tap cap\n")
        ]
    },
    {
        'id': 'e',
        'name': 'Cumbre Galáctica',
        'pages': [7],
        'samples': [
            ("3\n2 1 3\n1 2 3\n1 2 3\n2 1 3\n1 2 3\n1 2 3\n", "1 2\n2 1\n3 3\n"),
            ("3\n3 2 1\n3 2 1\n3 2 1\n1 2 3\n2 1 3\n3 2 1\n", "1 1\n2 2\n3 3\n")
        ]
    },
    {
        'id': 'f',
        'name': 'Comunicación en un Mundo Hostil',
        'pages': [8, 9],
        'samples': [
            ("4 5\n0 0 5\n0 4 5\n12 11 5\n4 4 5\nA 2 4\nB 1 3\nC 1 2\nD 1 1\nE 3 4\n", "B C D\nA B C\nB C D\nA B E\n"),
            ("6 3\n11 7 4\n-5 3 12\n0 0 11\n1 3 4\n-12 -14 20\n-7 2 12\nC 1 1\nJ 1 2\nM 2 12\n", "C J\nC J\nJ M\nM\nM\nM\n")
        ]
    },
    {
        'id': 'g',
        'name': 'El Duelo en la Estrella de la Muerte',
        'pages': [10],
        'samples': [
            ("8\n2 2 1 1\n3 3 2 2\n2 7 1 4\n2 7 2 2\n8 9 4 6\n9 9 5 5\n2 20 2 11\n22 99 20 70\n", "2\n4\n4\n3\n6\n8\n6\n10\n")
        ]
    }
]

def main():
    base_dir = '/home/rafael/Desktop/ucv/judge'
    problems_dir = os.path.join(base_dir, 'problems')
    os.makedirs(problems_dir, exist_ok=True)
    
    pdf_path = os.path.join(base_dir, 'problems.pdf')
    if os.path.exists(pdf_path):
        reader = PdfReader(pdf_path)
    else:
        print("problems.pdf not found!")
        return

    for prob in problems:
        pid = prob['id']
        pdir = os.path.join(problems_dir, pid)
        os.makedirs(pdir, exist_ok=True)
        
        # Write problem.yaml
        yaml_path = os.path.join(pdir, 'problem.yaml')
        with open(yaml_path, 'w', encoding='utf-8') as f:
            f.write(f'name: "{prob["name"]}"\n')
            f.write('limits:\n')
            f.write('  memory: 128\n')
            if pid in ['c', 'd', 'e', 'g']:
                f.write('  time_multiplier: 5.0\n')
                
        # Write problem.pdf
        writer = PdfWriter()
        for pnum in prob['pages']:
            writer.add_page(reader.pages[pnum])
        with open(os.path.join(pdir, 'problem.pdf'), 'wb') as f:
            writer.write(f)
            
        # Write sample data
        sample_dir = os.path.join(pdir, 'data', 'sample')
        os.makedirs(sample_dir, exist_ok=True)
        
        for i, (inp, ans) in enumerate(prob['samples'], 1):
            with open(os.path.join(sample_dir, f'{i}.in'), 'w', encoding='utf-8') as f:
                f.write(inp)
            with open(os.path.join(sample_dir, f'{i}.ans'), 'w', encoding='utf-8') as f:
                f.write(ans)
                
        # Create ZIP file
        zip_path = os.path.join(problems_dir, f'{pid}.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(pdir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, pdir)
                    zf.write(file_path, arcname)
                    
        print(f"Created {pid}.zip successfully.")

if __name__ == "__main__":
    main()